#!/usr/bin/env python3
"""
===== Interview Agent 全流程演示 =====
演示 4 大 Skill 的完整操作流程，使用预生成的模拟数据展示所有界面效果。
"""
from __future__ import annotations
import sys
import json
import os
from datetime import datetime
from pathlib import Path

# 确保根目录在 path 中
sys.path.insert(0, str(Path(__file__).parent))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree
from rich import box
from rich.text import Text
from rich.markdown import Markdown

from core.storage import StorageManager

console = Console()

DEMO_DIR = Path(__file__).parent / "demo_files"
DATA_DIR = Path(__file__).parent / "data"

# ======== 模拟数据 ========

MOCK_RESUME_EXTRACT = {
    "type": "resume",
    "data": {
        "name": "张明",
        "title": "飞书高级产品经理",
        "summary": "5年B端产品经验，专注企业协作/SaaS领域。主导飞书审批流引擎重构，实现60%效率提升。有丰富的多租户权限体系、开放平台产品设计经验，具备团队管理能力。",
        "education": [
            {"school": "北京大学", "degree": "本科", "major": "信息管理与信息系统", "year": "2014-2018"},
            {"school": "清华大学", "degree": "硕士", "major": "管理科学与工程", "year": "2018-2020"},
        ],
        "work_experience": [
            {"company": "字节跳动", "role": "飞书高级产品经理", "period": "2022.04-至今",
             "highlights": ["飞书审批模块产品规划", "审批流引擎重构效率提升60%", "搭建审批数据体系", "管理3人团队"]},
            {"company": "腾讯", "role": "企业微信B端产品经理", "period": "2020.07-2022.03",
             "highlights": ["API开放平台设计", "第三方应用接入规范", "开发者社区运营"]},
        ],
        "skills": ["SaaS产品设计", "权限体系设计", "工作流引擎", "数据分析", "项目管理", "团队管理", "开放平台"],
        "projects_overview": ["飞书审批流可视化配置引擎", "多租户权限体系设计"],
    }
}

MOCK_PROJECT_EXTRACT = {
    "type": "project",
    "data": {
        "name": "飞书审批流可视化配置引擎重构",
        "role": "产品负责人",
        "background": "飞书审批模块日均审批单量100万+，原有JSON配置方式门槛高、错误率30%",
        "problem": "配置门槛高，错误率高，调试困难，每次变更依赖研发",
        "solution": "可视化拖拽编辑器+条件配置面板+实时预览+模板市场+变更影响分析",
        "my_contribution": "深度访谈20+企业客户、30+原型迭代、双周sprint管理、A/B测试机制",
        "results": [
            "流程配置效率提升60%（4h→1.5h）",
            "配置错误率降低45%",
            "NPS从32提升至68",
            "企业客户满意度提升25pp",
        ],
        "metrics": [
            {"name": "配置效率", "value": "+60%", "description": "平均配置时间从4小时降至1.5小时"},
            {"name": "错误率", "value": "-45%", "description": "从30%降至16.5%"},
            {"name": "NPS", "value": "32→68", "description": "满意度大幅提升"},
        ],
        "skills_used": ["B端产品设计", "用户研究", "数据分析", "项目管理"],
        "tags": ["审批流", "可视化", "SaaS", "企业服务"],
    }
}

MOCK_JD_EXTRACT = {
    "type": "jd",
    "data": {
        "company": "字节跳动",
        "position": "资深B端产品经理（商业化方向）",
        "department": "飞书商业化中心",
        "responsibilities": [
            "飞书商业化产品规划与迭代，对商业收入指标负责",
            "深入理解企业客户需求，输出高质量产品方案",
            "协同销售/CSM/研发推动产品全流程",
            "建立数据监控体系，数据驱动决策",
            "参与重点客户售前支持",
        ],
        "requirements": [
            "5年以上B端产品经验，SaaS经验优先",
            "熟悉B端商业逻辑（定价/GTM/客户成功）",
            "出色的逻辑思维与数据分析能力",
            "优秀的跨部门沟通与项目管理能力",
            "有企业协作/办公/HR领域经验者优先",
        ],
        "preferred": [
            "从0到1商业化产品经验",
            "飞书生态深度使用经验",
            "团队管理经验",
        ],
        "industry": "SaaS/企业服务",
    }
}

MOCK_PROFILE = {
    "name": "张明",
    "target_positions": ["资深B端产品经理（商业化方向）", "B端产品专家", "SaaS产品负责人"],
    "current_title": "飞书高级产品经理",
    "years_of_experience": 5,
    "education": [
        {"school": "北京大学", "degree": "本科", "major": "信息管理与信息系统"},
        {"school": "清华大学", "degree": "硕士", "major": "管理科学与工程"},
    ],
    "core_skills": [
        "SaaS产品设计", "权限体系设计", "工作流引擎",
        "数据分析", "项目管理", "跨部门协作", "B端商业化",
    ],
    "career_summary": "5年B端企业级产品经验，在审批流引擎、权限体系、开放平台领域有深度实践",
    "key_projects": [
        {"name": "飞书审批流可视化引擎重构", "role": "产品负责人",
         "metrics": ["效率提升60%", "错误率降低45%", "NPS 32→68"]},
        {"name": "多租户权限体系设计", "role": "产品负责人",
         "metrics": ["支撑500+企业", "配置时间从3天→2小时"]},
    ],
    "b2b_domain_expertise": [
        "企业协作SaaS", "审批/工作流引擎", "权限体系（RBAC）",
        "开放平台/API产品", "B端商业化",
    ],
    "highlight_achievements": [
        "主导飞书审批流引擎重构，效率提升60%覆盖500+企业",
        "设计多租户权限体系将配置时间从3天缩短至2小时",
        "运营5000+开发者的API开放平台，接入应用增长200%",
    ],
    "weak_areas": [
        "商业化产品经验（偏工具型产品，缺少定价/GTM经历）",
        "缺少从0到1搭建商业化产品的完整经验",
        "数据科学深度（SQL/Python基础水平需加强）",
    ],
    "source_files": ["resume_张明.txt", "飞书审批模块重构项目文档.txt", "字节跳动B端产品经理JD.txt"],
}

MOCK_PREP_RESULT = """
## 字节跳动 资深B端产品经理（商业化方向）准备材料

### 一、岗位核心要求分析
该岗位最看重三项能力：
1. **商业化思维**（核心差异点）— 从工具型PM转型为商业PM，需要对定价、GTM、收入指标有感觉
2. **企业客户深度理解** — 能搞定中大型企业的复杂需求
3. **数据驱动决策** — 建立体系、看数据做判断

### 二、候选人匹配度分析

| 维度 | 匹配度 | 说明 |
|------|--------|------|
| B端产品经验 | ★★★★★ | 5年B端，飞书+企微双重背景 |
| 企业客户理解 | ★★★★★ | 深度服务500+企业，访谈20+客户 |
| 工作流/办公领域 | ★★★★★ | 审批流引擎是核心经历 |
| 商业化经验 | ★★☆☆☆ | ⚠️ 短板：缺少定价/GTM实战 |
| 从0到1经验 | ★★★☆☆ | 权限体系是从0到1，但非商业化产品 |
| 数据分析 | ★★★★☆ | 搭建过体系，但深度工具能力有限 |

### 三、高频面试题预测

**商业化类（高概率）**
1. "飞书审批目前怎么收费的？如果是你，会怎么优化定价策略？"
   → 考察商业化思维、定价逻辑

2. "假设飞书审批要推一个高级版，你觉得应该包含什么功能？定什么价？"
   → 考察GTM策略、价值包装

3. "你怎么定义商业化产品经理和工具型产品经理的区别？"
   → 考察角色认知

**项目深挖类**
4. "审批流引擎重构中，你怎么衡量'成功'？具体用了哪些指标？"
   → 考察数据意识和量化思维

5. "多租户权限体系设计中最难的技术决策是什么？"
   → 考察架构理解和决策能力

**行为面试类（STAR-PA）**
6. "讲一个你推动跨团队协作并遇到阻力的案例"
   → 考察沟通推进能力

7. "如果资源受限，你怎么决定做什么和不做什么？"
   → 考察优先级判断

### 四、准备策略建议

**重点补强：商业化**
- 研究飞书现有定价模型（官网可查）
- 学习 SaaS 定价框架：value-based pricing、usage-based、tiered
- 准备一个"商业化假设"——如果是你，会怎么优化飞书审批的价格体系
- 准备说辞：虽然缺少商业化title，但在审批重构中已经关注了功能→价值的转化

**项目表述优化**
- 审批流重构不需要说太多技术细节，重点表述这个功能为企业客户创造了什么价值
- 把数据指标对齐到商业语言：效率提升→人力成本节约→客户续费意愿

**行为面试准备**
- 按STAR-PA框架准备3个核心案例：跨部门协作、数据驱动决策、资源受限下的取舍
- 每个案例要有量化结果（数字！）
"""

MOCK_QA_SESSION = [
    ("用户", "我注意到这个岗位要求商业化方向，但我之前偏产品工具方向，面试时怎么弥补这个gap？"),
    ("助手", """**问题分析**：这是在考察你的自我认知和转型意愿，面试官想看到你清楚自己的短板且有准备。

**答题策略：**

**1. 承认差距但不自卑**
> "确实，我过去偏产品工具方向，但我认为商业化PM的底层能力是相同的——都是发现需求、定义价值、推动落地。区别在于价值衡量的维度变了。"

**2. 展示商业化思维的证据**
虽然title不是商业化，但你的实际工作中已经有了商业化的影子：
- 审批流引擎重构中，核心关注的是**企业客户的付费意愿**（功能→效率→成本节约→续费）
- 与商业化团队协作定义**企业版的定价层级**
- 重点客户的售前支持（说明你参与过商业化转化过程）

**3. 表达学习意愿+实际行动**
> "我最近正在系统学习SaaS定价框架和GTM策略，同时研究主流竞品（如钉钉、企微）的商业模式差异。"

**参考话术框架：**
```
我认为商业化和工具的边界是模糊的。我在飞书审批模块的工作中，
做的不是纯粹的'功能堆砌'，而是持续思考什么功能客户愿意付费、
企业版和个人版的差异化价值在哪。比如在审批流重构时，
我主动和商业化团队梳理了功能分级策略，最终将'高级审批链配置'
作为企业版的差异化能力。这个过程中我意识到，商业化PM的核心
是找到产品价值与商业价值的交点——而这正是我擅长的。
```
"""),
    ("用户", "面试时问到'你做过最失败的项目是什么'，我怎么回答才不掉分？"),
    ("助手", """**问题分析**：这是行为面试中的经典题，面试官看的是：
1. 你是否有反思复盘的习惯
2. 你能否识别真正的问题（不是甩锅）
3. 从失败中学到了什么

**推荐结构（STAR-PA变体）：**

**S/T**：我在腾讯企微时，负责API开放平台的开发者工具上线
**A1 问题**：工具上线后开发者采用率很低（目标30%，实际8%）
**why**：我们假设开发者需要的是"更强大的调试工具"，但实际他们需要的是"接入门槛更低"

**A2 调整**：- 主动约访10个开发者做深度访谈
- 发现核心痛点不是工具不好用，而是文档太难理解
- 转向投入产出比更高的方向：文档重构+交互式教程

**R/P**：- 半年内活跃开发者从2000→5000+
- 反思：犯了"解决方案先行"的错误，应该先验证问题再投入

**用你的真实项目：**
```
在飞书审批流引擎重构中，我早期犯了同样的错误。
最开始团队都在讨论'用什么样的可视化技术'，
但我访谈了3家客户后发现，最痛的根本不是'不好看'，
而是'配置逻辑太复杂看不懂'。
这个经历让我养成了做任何产品决策前先验证问题的习惯。
```
"""
    ),
]


def step(title: str, subtitle: str = ""):
    """打印步骤标题"""
    console.rule(f"[bold cyan]{title}[/bold cyan]")
    if subtitle:
        console.print(f"[dim]{subtitle}[/dim]\n")


def seed_demo_data(storage: StorageManager):
    """预填充演示数据到本地存储"""
    storage.save_json("materials/index.json", {
        "resumes": [{"file": "resume_张明.txt", "type": "resume", "title": "张明 — 飞书高级产品经理",
                     "imported_at": datetime.now().isoformat()}],
        "projects": [{"file": "飞书审批模块重构项目文档.txt", "type": "project", "title": "飞书审批流可视化配置引擎重构",
                      "imported_at": datetime.now().isoformat()}],
        "jds": [{"file": "字节跳动B端产品经理JD.txt", "type": "jd", "title": "字节跳动 资深B端产品经理（商业化方向）",
                 "imported_at": datetime.now().isoformat()}],
        "notes": [],
        "updated_at": datetime.now().isoformat(),
    })
    storage.save_profile_data(MOCK_PROFILE)


def print_extract_preview(label: str, data: dict, color: str):
    """显示导入提取结果预览"""
    text = json.dumps(data, ensure_ascii=False, indent=2)
    console.print(Panel(text[:1200], title=f"📥 {label} — LLM 提取结果", border_style=color))


# ======== 主流程 ========

def main():
    console.clear()

    # ── 封面 ──
    console.print(Panel.fit(
        "[bold cyan]🎯 B端产品经理面试助手 — 全流程演示[/bold cyan]\n\n"
        "[dim]本演示使用预置模拟数据，展示完整的 4 大 Skill 流程。[/dim]\n"
        "[dim]正式使用时只需设置 ANTHROPIC_API_KEY 即可对接真实 LLM。[/dim]",
        border_style="cyan",
    ))
    console.print()

    # 初始化存储
    storage = StorageManager(base_dir=str(DATA_DIR))
    seed_demo_data(storage)

    # ────────────────────────────────────────────────
    # PHASE 1: 素材库管理 — material
    # ────────────────────────────────────────────────
    step("Phase 1: 素材库导入与整理", "material import → list → profile")

    # 1.1 导入简历
    console.print(Panel(
        "[bold]mock start material import demo_files/resume_张明.txt[/bold]\n\n"
        "系统自动检测文件类型 → 复制到素材库 → LLM 提取结构化信息 → 更新索引",
        border_style="blue",
    ))
    print_extract_preview("简历", MOCK_RESUME_EXTRACT, "green")
    console.print("\n")

    # 1.2 导入项目
    console.print(Panel(
        "[bold]mock start material import demo_files/项目文档.txt[/bold]",
        border_style="blue",
    ))
    print_extract_preview("项目文档", MOCK_PROJECT_EXTRACT, "cyan")
    console.print("\n")

    # 1.3 导入 JD
    console.print(Panel(
        "[bold]mock start material import demo_files/JD.txt[/bold]",
        border_style="blue",
    ))
    print_extract_preview("岗位描述 (JD)", MOCK_JD_EXTRACT, "magenta")
    console.print("\n")

    # 1.4 material list
    step("material list — 素材分类展示")
    tree = Tree("[bold]📂 素材库[/bold]")
    resumes = tree.add("[bold]📄 简历 (1)[/bold]")
    resumes.add("resume_张明.txt  [dim]4KB[/dim]")
    projects = tree.add("[bold]📁 项目文档 (1)[/bold]")
    projects.add("飞书审批模块重构项目文档.txt  [dim]3KB[/dim]")
    jds = tree.add("[bold]🎯 岗位描述 (1)[/bold]")
    jds.add("字节跳动B端产品经理JD.txt  [dim]2KB[/dim]")
    tree.add("[bold]👤 候选人画像[/bold]")
    console.print(tree)
    console.print()

    # 1.5 material profile
    step("material profile — 生成候选人画像")

    from rich.markup import escape
    profile = MOCK_PROFILE
    lines = [
        f"姓名: {profile['name']}",
        f"目标岗位: {', '.join(profile['target_positions'])}",
        f"当前职位: {profile['current_title']}    经验: {profile['years_of_experience']} 年",
        "",
        "核心技能:",
    ]
    for s in profile['core_skills']:
        lines.append(f"  * {s}")
    lines.append("")
    lines.append("B端领域专长:")
    for d in profile['b2b_domain_expertise']:
        lines.append(f"  * {d}")
    lines.append("")
    lines.append("关键项目:")
    for p in profile['key_projects']:
        metrics = " | ".join(p["metrics"])
        lines.append(f"  * {p['name']}（{p['role']}）— {metrics}")
    lines.append("")
    lines.append("亮点成就:")
    for a in profile['highlight_achievements']:
        lines.append(f"  V {a}")
    lines.append("")
    lines.append("需加强:")
    for w in profile['weak_areas']:
        lines.append(f"  X {w}")

    console.print(Panel("\n".join(lines), title="📋 候选人画像", border_style="cyan"))
    console.print()

    # ────────────────────────────────────────────────
    # PHASE 2: 面试准备 — prep
    # ────────────────────────────────────────────────
    step("Phase 2: 面试准备", "prep for → prep ask（多轮互动）")

    # 2.1 prep for
    console.print(Panel(
        "[bold]prep for 字节跳动 资深B端产品经理（商业化方向）[/bold]\n",
        border_style="green",
    ))
    console.print(Markdown(MOCK_PREP_RESULT))
    console.print()

    # 2.2 prep ask (多轮问答)
    step("prep ask — 多轮互动对话", "基于素材回答你的问题，支持持续追问")

    for i, (role, content) in enumerate(MOCK_QA_SESSION):
        if role == "用户":
            console.print(Panel(
                f"[bold]Q: {content}[/bold]",
                title=f"🙋 你 (第 {i//2+1} 轮)",
                border_style="yellow",
            ))
        else:
            console.print(Panel(
                Markdown(content),
                title="💡 面试准备助手",
                border_style="green",
            ))
        console.print()

    # ────────────────────────────────────────────────
    # PHASE 3: 模拟面试 — mock
    # ────────────────────────────────────────────────
    step("Phase 3: 模拟面试", "mock start → mock answer → mock hint → mock review")

    # 3.1 mock start
    console.print(Panel(
        "[bold]mock start 字节跳动 资深B端产品经理（商业化方向）[/bold]",
        border_style="red",
    ))
    console.print(Panel(
        "你好，我是字节飞书商业化团队的产品负责人，今天面试张明同学。\n\n"
        "面试大约40分钟，我会问5-6个问题。先请你做个简短的自我介绍，重点说说你在飞书审批\n"
        "模块的工作经历，以及你认为商业化产品经理和工具型产品经理的核心区别是什么。\n\n"
        "你可以开始了。",
        title="🎙️ 字节跳动 面试官",
        border_style="red",
    ))
    console.print("\n")

    # 3.2 answer + 追问
    console.print(Panel(
        "我在飞书负责审批模块近2年，主导了审批流引擎重构，从JSON配置改为可视化拖拽，\n"
        "效率提升60%。关于商业化PM和工具PM的区别，我认为工具PM关注功能和体验，\n"
        "商业化PM关注价值转化。在审批重构中，我逐渐意识到同样的功能对企业客户的价值\n"
        "不同，应该根据价值定价。",
        title="🙋 你的回答",
        border_style="yellow",
    ))
    console.print()

    console.print(Panel(
        "很好的回答。你提到了价值定价，能具体说说在审批重构过程中，你做了哪些事情\n"
        "来识别'哪些功能对企业客户更有价值'？另外，如果让你设计飞书审批的高级版，\n"
        "你会包含哪3个差异化功能？",
        title="🎙️ 面试官 — 追问",
        border_style="red",
    ))
    console.print()

    # 3.3 hint
    console.print(Panel(
        "[bold]mock hint[/bold]（请求提示）",
        border_style="yellow",
    ))
    console.print(Panel(
        "💡 **答题提示**\n\n"
        "**第一问（价值识别）：** 用 STAR-PA 框架\n"
        "- 情况：访谈了20+企业客户，发现大型企业最痛的是复杂的审批链\n"
        "- 行动：建立功能需求分级矩阵（使用频率×客户付费意愿）\n"
        "- 结论：高级审批链配置→企业版差异化能力\n\n"
        "**第二问（高级版设计）：** 从三个维度思考\n"
        "1. 效率提升：智能审批助手（AI规则推荐）\n"
        "2. 管控增强：跨部门审批链模板+合规审计\n"
        "3. 数据分析：审批效率看板+组织效能报告",
        title="💡 抖音面试官提示",
        border_style="yellow",
    ))
    console.print("\n")

    # 3.4 mock end
    console.print(Panel(
        "好的时间关系，我们先到这里。最后你有什么想问我的吗？",
        title="🎙️ 面试官",
        border_style="red",
    ))
    console.print()

    console.print(Panel(
        "[bold]mock end[/bold]\n\n"
        "面试已结束。共回答 3 题。\n"
        "输入 mock review 查看评估报告。",
        border_style="yellow",
    ))
    console.print()

    # 3.5 mock review
    step("mock review — 评估报告")

    MOCK_EVALUATION = {
        "overall_score": 7.2,
        "dimension_scores": {"逻辑架构": 8, "B端思维": 8, "数据意识": 7, "岗位匹配度": 6, "表达质量": 7},
        "strengths": [
            "项目经历充实，审批流重构有具体量化数据支撑",
            "B端思维扎实，能区分不同角色和多层级的需求",
            "逻辑表达清晰，有结构化回答的意识",
        ],
        "weaknesses": [
            "商业化维度回答偏虚，缺少具体定价/GTM策略的思考",
            '对"识别价值"的问题回答不够深入，缺少系统性方法论',
            "自我介绍的切入点可以更精准地对齐岗位要求",
        ],
        "priority_improvements": [
            {"area": "商业化思维", "suggestion": "提前研究飞书的定价模型，准备3个定价优化的具体建议", "priority": "高"},
            {"area": "价值识别方法论", "suggestion": "学习jobs-to-be-done框架，能用它分析企业对审批功能的需求层次", "priority": "高"},
            {"area": "自我介绍结构", "suggestion": "用'30s定位+2min经历+30s动机'结构，30s内点出与商业化岗位的关联", "priority": "中"},
        ],
        "sample_answer": """## 示范：价值识别的完整回答

**背景：** 我在推动审批流引擎重构时，没有直接开始设计，而是先做了3件事：
1. **分层调研**：访谈了20家企业客户的审批负责人、IT管理员、HR负责人，覆盖3个决策角色
2. **需求分级**：用RICE模型给每个需求打分，发现"复杂审批链"虽然使用频率低（仅20%客户用到），但付费意愿极高
3. **验证假设**：做了MVP原型让5个典型客户试用，验证了价值判断

**结论：** 工具PM和价值PM的区别在于——工具PM看功能的操作效率，商业化PM看功能对客户业务的价值层次。同一个审批功能，对10人公司是便利，对5000人公司是合规，后者愿意为此付10倍价格。""",
        "summary": "有扎实的B端产品基础和量化意识，但商业化的思维框架需要加强。建议重点准备定价策略和价值识别的方法论。",
    }

    e = MOCK_EVALUATION

    # 总分
    score_color = "green" if e["overall_score"] >= 7 else "yellow" if e["overall_score"] >= 5 else "red"
    console.print(f"[bold]公司:[/bold] 字节跳动  [bold]岗位:[/bold] 资深B端产品经理（商业化方向）")
    console.print(f"[bold]回答题数:[/bold] 3")
    console.print(f"\n[bold {score_color}]总分: {e['overall_score']}/10[/bold {score_color}]")

    # 维度分
    table = Table(box=box.SIMPLE)
    table.add_column("维度", style="cyan")
    table.add_column("评分", justify="center")
    table.add_column("等级")
    for dim, s in sorted(e["dimension_scores"].items(), key=lambda x: x[1]):
        stars = "★" * max(1, round(s / 3)) + "☆" * (3 - max(1, round(s / 3)))
        color = "green" if s >= 7 else "yellow" if s >= 5 else "red"
        table.add_row(dim, f"[{color}]{s}/10[/{color}]", stars)
    console.print(table)

    console.print(f"\n[bold green]优势:[/bold green]")
    for s in e["strengths"]:
        console.print(f"  ✓ {s}")
    console.print(f"\n[bold red]待改进:[/bold red]")
    for w in e["weaknesses"]:
        console.print(f"  ✗ {w}")

    console.print(f"\n[bold]改进建议:[/bold]")
    for imp in e["priority_improvements"]:
        ptag = {"高": "[red]高[/red]", "中": "[yellow]中[/yellow]", "低": "[dim]低[/dim]"}.get(imp["priority"])
        console.print(f"  [{ptag}] [bold]{imp['area']}[/bold]: {imp['suggestion']}")

    console.print(f"\n[bold]💡 示范回答:[/bold]")
    console.print(Panel(Markdown(e["sample_answer"][:600]), border_style="blue"))
    console.print(f"\n[bold]总结:[/bold] {e['summary']}")
    console.print()

    # ────────────────────────────────────────────────
    # PHASE 4: 面试追踪 — tracker
    # ────────────────────────────────────────────────
    step("Phase 4: 面试追踪", "tracker add → list → stats")

    # 4.1 预填充面试记录
    seed_records = [
        {"id": 1, "company": "字节跳动", "position": "资深B端产品经理（商业化）", "round": "一面",
         "status": "有结果", "result": "通过", "interview_date": "2026-04-15",
         "experience": "问了商业化思维和审批流重构，重点在价值识别", "notes": "", "created_at": "2026-04-10T10:00:00",
         "updated_at": "2026-04-16T10:00:00"},
        {"id": 2, "company": "字节跳动", "position": "资深B端产品经理（商业化）", "round": "二面",
         "status": "待面试", "result": "", "interview_date": "2026-04-22",
         "experience": "", "notes": "准备商业化案例", "created_at": "2026-04-16T11:00:00",
         "updated_at": "2026-04-16T11:00:00"},
        {"id": 3, "company": "钉钉", "position": "高级B端产品经理", "round": "HR面",
         "status": "有结果", "result": "挂", "interview_date": "2026-04-10",
         "experience": "HR面聊了离职动机和职业规划，感觉回答不够有说服力", "notes": "", "created_at": "2026-04-05T09:00:00",
         "updated_at": "2026-04-11T10:00:00"},
        {"id": 4, "company": "腾讯", "position": "企业微信B端产品组长", "round": "一面",
         "status": "已面试", "result": "待定", "interview_date": "2026-04-18",
         "experience": "面了1.5小时，系统设计题偏多，要补系统设计", "notes": "", "created_at": "2026-04-15T14:00:00",
         "updated_at": "2026-04-18T17:00:00"},
        {"id": 5, "company": "飞书", "position": "商业化产品专家", "round": "一面",
         "status": "有结果", "result": "通过", "interview_date": "2026-05-06",
         "experience": "面了商业化案例分析和定价策略", "notes": "感觉不错", "created_at": "2026-04-28T10:00:00",
         "updated_at": "2026-05-07T10:00:00"},
        {"id": 6, "company": "飞书", "position": "商业化产品专家", "round": "二面",
         "status": "待面试", "result": "", "interview_date": "2026-05-15",
         "experience": "", "notes": "准备GTM案例", "created_at": "2026-05-07T11:00:00",
         "updated_at": "2026-05-07T11:00:00"},
    ]
    storage.save_interviews(seed_records)

    # 4.2 tracker list
    console.print(Panel("[bold]tracker list[/bold]", border_style="magenta"))
    table = Table(title="面试记录 (6 条)", box=box.SIMPLE)
    table.add_column("ID", style="dim", width=4)
    table.add_column("公司", style="cyan")
    table.add_column("岗位")
    table.add_column("轮次", width=8)
    table.add_column("状态", width=8)
    table.add_column("结果", width=6)
    table.add_column("面试日期")
    for r in reversed(seed_records):
        sc = {"待面试": "yellow", "已面试": "blue", "有结果": "green"}.get(r["status"], "white")
        rc = {"通过": "green", "offer": "green", "挂": "red", "待定": "yellow"}.get(r["result"], "white")
        table.add_row(str(r["id"]), r["company"], r["position"], r["round"],
                       f"[{sc}]{r['status']}[/{sc}]", f"[{rc}]{r['result']}[/{rc}]" if r["result"] else "",
                       r["interview_date"])
    console.print(table)
    console.print()

    # 4.3 tracker stats
    step("tracker stats — 统计看板")
    console.print(Panel(f"""
[bold]📊 面试统计看板[/bold]

[bold]总体数据:[/bold]
  总记录: 6
  待面试: 2
  已完成面试: 4
  通过/Offer: 2
  已挂: 1
  待定: 1

[bold]面试转化率:[/bold]
  一面通过率: 67%（通过2/面试3）
  整体进展: 2 家进入二面 / 1 家 offer 流程

[bold]轮次分布:[/bold]
  一面: 4 次
  二面: 1 次
  HR面: 1 次

[bold]投递公司:[/bold]
  字节跳动: 2 次
  飞书: 2 次
  钉钉: 1 次
  腾讯: 1 次
    """.strip(), title="📈 面试统计", border_style="magenta"))
    console.print()

    # ── 总结 ──
    console.rule("[bold cyan]演示结束[/bold cyan]")
    console.print(Panel(
        "[bold]完整流程已演示完毕 ✅[/bold]\n\n"
        "演示的 4 大模块:\n"
        "  📂 素材库管理 — 导入 → 归类 → 搜索 → 画像合成\n"
        "  📖 面试准备 — 定制学习材料 → 多轮互动问答\n"
        "  🎯 模拟面试 — 角色扮演 → 答题 → 提示 → 5维评估\n"
        "  📊 面试追踪 — 记录 → 列表 → 统计看板\n\n"
        "[bold]正式使用只需:[/bold]\n"
        "  export ANTHROPIC_API_KEY=sk-xxx\n"
        "  cd /Users/lulu/interview-agent && python3 agent.py\n\n"
        "[dim]代码文件以真实生产质量编写，可直接运行使用。[/dim]",
        border_style="cyan",
    ))


if __name__ == "__main__":
    main()
