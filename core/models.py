"""Interview Agent 数据模型 — 全部使用 dataclass + 纯 JSON 序列化

═══════════════════════════════════════════════════════════════════════════════
架构设计说明（AI 产品经理视角）
═══════════════════════════════════════════════════════════════════════════════

一、为什么用 dataclass 而不是 Pydantic？

  1. dataclass 是 Python 标准库，零额外依赖
  2. 不需要运行时校验（数据来自 LLM 输出或本地 JSON，不是外部不可信输入）
  3. 序列化/反序列化用 asdict() 和 ** 展开，简单直接

  Pydantic 的优势（schema 校验、类型强制转换）在这个场景中用不上，
  引入只会增加依赖和心智负担。

二、模型分层设计

  ┌─────────────────────────────────────────┐
  │  素材层（ResumeInfo / ProjectInfo / JDInfo） │  ← LLM 从文件中提取的结构化数据
  ├─────────────────────────────────────────┤
  │  画像层（UserProfile）                    │  ← 从多份素材合成的候选人全景图
  ├─────────────────────────────────────────┤
  │  面试层（MockSession / MockQuestion / MockAnswer）│  ← 模拟面试的运行时状态
  ├─────────────────────────────────────────┤
  │  追踪层（InterviewRecord）               │  ← 真实面试记录与复盘
  └─────────────────────────────────────────┘

  上层可以引用下层的数据，但下层不会感知上层存在。
  例如 MockSession 不依赖 UserProfile，而是从 _selected_resume_path 自己读素材。

三、为什么 to_dict() 是手写而不是统一抽象？

  部分模型（MockSession、MockAnswer）包含嵌套 dataclass 列表，
  需要递归调用 to_dict()。统一基类做这件事需要引入反射或泛型，
  vs 手写三个模型的 to_dict() 更直接，出问题一眼能看出来。

四、字段的默认值设计原则

  所有字段都有默认值（空字符串、空列表、0），这样：
    - 从 JSON 反序列化时，缺失字段不会报错
    - LLM 输出不稳定时，部分字段缺失不影响整体流程
    - 新老版本 JSON 兼容：老数据没有新字段时自动用默认值

  代价是不能区分 "未填写" 和 "真的为空"，但这个场景不需要。
═══════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import datetime


# ═══════════════════════════════════════════════════════════════════════════
# 素材层：LLM 从用户上传的文件中提取的结构化信息
# 每一个模型对应一种素材类型，字段设计参考了招聘行业通用标准
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ResumeInfo:
    """简历信息 — LLM 从简历文件中提取的候选人结构化数据。

    与标准招聘系统简历字段对齐，但做了简化：
      - work_experience 用 list[dict] 而非独立模型，灵活适配不同简历格式
      - skills 是字符串列表，不做技能等级评估（那是画像层的事）
    """
    name: str = ""                          # 候选人姓名
    title: str = ""                         # 当前职位（如"高级B端产品经理"）
    summary: str = ""                       # 个人简介/自我评价（LLM 提取摘要）
    education: list[dict] = field(default_factory=list)  # [{school, degree, major, year}]
    work_experience: list[dict] = field(default_factory=list)  # [{company, role, period, highlights}]
    skills: list[str] = field(default_factory=list)       # 技能标签列表
    projects_overview: list[str] = field(default_factory=list)  # 项目名称列表（详细内容在 ProjectInfo）


@dataclass
class ProjectInfo:
    """项目信息 — 单个产品的完整复盘数据。

    字段设计遵循「STAR 法则」改造版，方便面试复盘：
      - background: Situation + Task（背景 + 任务）
      - problem + solution: Action（问题 + 解决方案）
      - results + metrics: Result（成果 + 量化指标）

    面试官通常问："你在这个项目里做了什么？效果怎么样？"
    这个模型的两个核心字段 my_contribution 和 metrics 就是为这类问题准备的。
    """
    name: str = ""                          # 项目名称
    role: str = ""                          # 项目中的角色（如"产品负责人"）
    background: str = ""                    # 项目背景（为什么做这个项目）
    problem: str = ""                       # 要解决的核心问题
    solution: str = ""                      # 产品解决方案概述
    my_contribution: str = ""               # 个人贡献（面试官最关心的部分）
    results: list[str] = field(default_factory=list)       # 定性成果列表
    metrics: list[dict] = field(default_factory=list)      # [{name, value, description}] 量化指标
    skills_used: list[str] = field(default_factory=list)   # 用到的技能
    tags: list[str] = field(default_factory=list)          # 标签（如"B端""SaaS""0-1"）


@dataclass
class JDInfo:
    """岗位描述信息 — LLM 从 JD 文件中提取的雇主需求结构化数据。

    字段设计参考招聘 JD 的标准分段：
      - responsibilities：工作职责（要做的事）
      - requirements：必须条件（硬性门槛）
      - preferred：加分项（有更好，没有也行）

    这三个维度的区分对面试准备很重要：
      - requirements 是面试必考题，必须准备
      - preferred 是区分度来源，拉开差距的地方
      - responsibilities 帮助理解岗位日常，判断自己是否真的想做
    """
    company: str = ""                       # 公司名称
    position: str = ""                      # 岗位名称
    responsibilities: list[str] = field(default_factory=list)   # 工作职责列表
    requirements: list[str] = field(default_factory=list)       # 必须条件列表
    preferred: list[str] = field(default_factory=list)          # 加分项列表
    department: str = ""                    # 归属部门
    industry: str = ""                      # 行业领域（如"企业服务""金融科技"）
    salary_range: str = ""                  # 薪资范围（如有，用于谈判参考）


@dataclass
class NoteInfo:
    """用户笔记 — 面试准备过程中的临时记录。

    与素材的区别：
      - 素材是原始文件（简历、JD），笔记是用户加工后的内容
      - 素材存储为物理文件 + 索引条目，笔记存储为独立 JSON 文件
      - 笔记可以标记来源（prep_skill 自动保存 / 用户手动记录）
    """
    title: str = ""                         # 笔记标题
    content: str = ""                       # 笔记正文
    source: str = ""                        # 来源标记（prep_skill / user / obsidian）
    tags: list[str] = field(default_factory=list)  # 标签
    created_at: str = ""                    # 创建时间（ISO 格式）


# ═══════════════════════════════════════════════════════════════════════════
# 画像层：从多份素材合成的候选人完整画像
# 这是整个 Agent 的核心资产 — 所有面试准备和模拟面试都基于此画像
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class UserProfile:
    """候选人完整画像 — Agent 从所有素材中合成的「人物全景图」。

    这是面试准备和模拟面试的数据基础。面试官角色的 system prompt
    会填充这个画像的信息，让模型扮演一个有背景知识的面试官。

    画像不是静态的：
      - 每次 material profile 命令会重新生成（覆盖）
      - 新增素材后画像会自动更新
      - 用户可以手动调整画像内容（profile.json 可直接编辑）

    关键字段说明：
      - b2b_domain_expertise：B 端领域专长，面试官重点追问方向
      - weak_areas：薄弱项，面试官可能针对性提问，也是备考重点
      - highlight_achievements：核心亮点，面试时主动引导到这个方向
    """
    name: str = ""                                          # 候选人姓名
    target_positions: list[str] = field(default_factory=list)  # 目标岗位列表
    current_title: str = ""                                 # 当前职位
    years_of_experience: int = 0                            # 工作年限（整数）
    education: list[dict] = field(default_factory=list)     # [{school, degree, major, year}]
    core_skills: list[str] = field(default_factory=list)    # 核心技能列表
    career_summary: str = ""                                # 职业生涯总结（LLM 生成，一段话）
    key_projects: list[dict] = field(default_factory=list)  # [{name, role, metrics}] 重点项目摘要
    b2b_domain_expertise: list[str] = field(default_factory=list)  # B 端领域专长
    highlight_achievements: list[str] = field(default_factory=list)  # 核心成就/亮点
    weak_areas: list[str] = field(default_factory=list)     # 薄弱项/待提升方向
    source_files: list[str] = field(default_factory=list)   # 画像来源的素材文件列表

    def to_dict(self) -> dict:
        """序列化为纯 dict，用于 JSON 存储。"""
        return asdict(self)


# ═══════════════════════════════════════════════════════════════════════════
# 面试层：模拟面试的运行时数据模型
# 这些模型记录一次完整模拟面试的全过程（题→答→评）
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class MockQuestion:
    """一道面试题 — 由 LLM 面试官在面试过程中生成。

    为什么不用 question bank（题库）：
      - 面试题应基于候选人画像和岗位 JD 动态生成，而非固定题库
      - 题库维护成本高且容易过时
      - 动态生成的题目有追问上下文，题库无法做到

    题目的 type 和 difficulty 由 LLM 自行判断，
    目前不强制分类，因为 LLM 的分类准确度大约 70%，强制校验会丢失信息。
    """
    question: str                           # 面试题文本（LLM 面试官的原话）
    type: str = ""                          # 题型（行为/估算/产品sense/策略/执行）
    difficulty: str = "中"                  # 难度（高/中/低）
    expected_framework: str = ""            # 预期的答题框架（STAR/金字塔/MECE 等）
    hint: str = ""                          # 该题的提示内容（用户请求 hint 时提供）

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MockAnswer:
    """一道题的回答 — 用户在模拟面试中提交的回答 + LLM 评分。

    score 和 feedback 在 mock review 阶段才会填充，
    面试过程中只看 question 和 answer。
    """
    question: str                           # 对应的面试题
    answer: str                             # 用户回答的原始文本
    score: float = 0.0                      # 评分（0-10，mock review 时填充）
    feedback: str = ""                      # 反馈（mock review 时 LLM 生成）
    suggestions: list[str] = field(default_factory=list)  # 改进建议列表

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MockSession:
    """一次完整的模拟面试会话 — 记录开始到结束的全过程。

    生命周期：
      进行中（mock start → 逐题问答） → 已完成（mock end / 自动达到最大题数）

    状态机：
      无 → [mock start] → 进行中 → [mock end / 满10题] → 已完成 → [mock review] → 有评分

    与 UI 的关系：
      - CLI 模式：通过 MockSkill 的状态字段判断当前在面试中还是结束后
      - Web 模式：通过 st.session_state.mock_started / mock_active 来跟踪 UI 状态
      - 两个模式的 session 数据共享同一套模型和存储
    """
    company: str = ""                       # 目标公司
    position: str = ""                      # 目标岗位
    questions: list[MockQuestion] = field(default_factory=list)  # 面试题列表（按提问顺序）
    answers: list[MockAnswer] = field(default_factory=list)      # 回答列表（一一对应）
    current_q_index: int = 0               # 当前题目序号（0-based）
    status: str = "进行中"                  # 会话状态：进行中 | 已完成
    summary: str = ""                       # 评估总结（mock review 时生成）
    overall_score: float = 0.0              # 总分（0-10）
    dimension_scores: dict = field(default_factory=dict)  # 各维度分数 {维度名: 分数}
    started_at: str = ""                    # 面试开始时间（ISO 格式）
    ended_at: str = ""                      # 面试结束时间（ISO 格式）

    def to_dict(self) -> dict:
        """序列化时递归处理嵌套的 dataclass 列表。"""
        return {
            "company": self.company,
            "position": self.position,
            "questions": [q.to_dict() for q in self.questions],
            "answers": [a.to_dict() for a in self.answers],
            "current_q_index": self.current_q_index,
            "status": self.status,
            "summary": self.summary,
            "overall_score": self.overall_score,
            "dimension_scores": self.dimension_scores,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
        }


# ═══════════════════════════════════════════════════════════════════════════
# 追踪层：真实面试记录（非模拟面试）
# 用于记录用户参加的真实面试，做复盘和趋势分析
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class InterviewRecord:
    """真实面试记录 — 用于追踪面试进展和复盘。

    与 MockSession 的区别：
      - MockSession 是 Agent 模拟的面试，InterviewRecord 是真实面试
      - InterviewRecord 有面试轮次、结果、面经等真实面试特有字段
      - MockSession 有评分和维度分析，InterviewRecord 只有文字记录

    面试进度追踪：
      待面试 → 已面试 → 有结果（通过/挂/待定/offer）
    """
    company: str = ""                       # 公司名称
    position: str = ""                      # 岗位名称
    interview_date: str = ""                # 面试日期
    round: str = "一面"                     # 面试轮次（一面/二面/三面/HR面/已offer/已挂）
    status: str = "待面试"                  # 当前状态（待面试/已面试/有结果）
    experience: str = ""                    # 面经/面试感受（自由文本）
    questions_recalled: list[str] = field(default_factory=list)  # 回忆的面试题
    result: str = ""                        # 面试结果（通过/挂/待定/offer）
    notes: str = ""                         # 补充笔记
    created_at: str = ""                    # 创建时间
    updated_at: str = ""                    # 最后更新时间

    def to_dict(self) -> dict:
        return asdict(self)


# ═══════════════════════════════════════════════════════════════════════════
# 搜索模型：统一的搜索结果格式
# 素材库搜索和 Obsidian 搜索都返回同一格式，方便前端统一渲染
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class SearchResult:
    """搜索结果 — 统一的跨来源搜索返回格式。

    不管是素材库本地搜索、Obsidian Vault 搜索、还是互联网搜索，
    最终都统一为 SearchResult 格式，方便 UI 层统一渲染搜索结果列表。
    """
    title: str = ""                         # 搜索结果标题
    url: str = ""                           # 文件路径或网页 URL
    content: str = ""                       # 摘要/上下文（截取关键部分，< 200 字符）

# ═══════════════════════════════════════════════════════════════════════════
# v2.0 新增模型：简历库 + 岗位库
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ResumeRecord:
    """简历记录 — 简历库中的单条简历元数据。

    PDF 文件存储在 data/resumes/ 目录，本 dataclass 仅存储元数据。
    """
    file_name: str                           # PDF 文件名
    file_path: str                           # PDF 文件绝对路径
    display_name: str = ""                   # 展示名称（用户可自定义，默认取文件名）
    uploaded_at: str = ""                    # 上传时间 ISO 格式

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ResumeRecord":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class PositionInfo:
    """岗位信息 — 岗位库中的单条结构化岗位数据。

    四个必填字段：公司名称、岗位名称、工作职责、任职要求。
    岗位数据存储在 data/positions/index.json 中。
    """
    company: str                             # 公司名称（必填）
    position: str                            # 岗位名称（必填）
    responsibilities: list[str] = None       # 工作职责列表（必填）
    requirements: list[str] = None           # 任职要求列表（必填）
    source: str = ""                         # 来源："manual" / "vision"
    source_image: str = ""                   # 如从图片提取，记录原图片路径
    created_at: str = ""                     # 创建时间 ISO 格式

    def __post_init__(self):
        if self.responsibilities is None:
            self.responsibilities = []
        if self.requirements is None:
            self.requirements = []

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "PositionInfo":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
    source: str = ""                        # 来源标识（素材库 / Obsidian / 网络搜索）
