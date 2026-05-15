"""技能调度器 — 解析用户意图并路由到对应 Skill"""
from __future__ import annotations
import re
from typing import Callable


# Skill 注册表
_skills: dict[str, object] = {}


def register(name: str, instance: object):
    """注册一个 Skill。"""
    _skills[name] = instance


def get_skill(name: str) -> object | None:
    return _skills.get(name)


def all_skills() -> dict[str, object]:
    return _skills


# ─── 命令解析 ──────────────────────────────────────────

def parse_command(text: str) -> tuple[str, str] | None:
    """
    解析显式命令。返回 (skill_name, args) 或 None。
    例如：
        material import /path/to/file  → ("material", "import /path/to/file")
        mock start 字节跳动 B端产品经理 → ("mock", "start 字节跳动 B端产品经理")
        /prep for 字节跳动              → ("prep", "for 字节跳动")
    """
    text = text.strip()

    # 支持 /skill 前缀
    if text.startswith("/"):
        text = text[1:]

    parts = text.split(maxsplit=1)
    skill_name = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    if skill_name in {"material", "prep", "mock", "tracker", "help"}:
        return (skill_name, args)
    return None


# ─── 意图分类 ──────────────────────────────────────────

_INTENT_PATTERNS = [
    (r"(导入|import|添加|上传|加入).*(简历|项目|文档|文件|素材)", "material", "import"),
    (r"(查看|列出|展示|list|ls).*(简历|项目|素材|文件|库)", "material", "list"),
    (r"(搜索|查找|找|search|find).*", "material", "search"),
    (r"(画像|profile|我的情况|综合情况)", "material", "profile"),

    (r"(准备|准备面试|prep).*(公司|岗位|面试)", "prep", "for"),
    (r"(问|提问|问题|ask|是什么|为什么|怎么做)", "prep", "ask"),
    (r"(搜索资料|查资料|查一下|search)", "prep", "search"),
    (r"(保存|记下来|存为笔记|save)", "prep", "save_note"),

    (r"(开始|开始面试|mock|模拟)", "mock", "start"),
    (r"(我的回答|回答|answer|答)", "mock", "answer"),
    (r"(提示|hint|思路|框架)", "mock", "hint"),
    (r"(结束|结束面试|stop|end)", "mock", "end"),
    (r"(评估|评分|review|评价|反馈)", "mock", "review"),

    (r"(记录|添加记录|面试记录|tracker).*(添加|新增|记)", "tracker", "add"),
    (r"(查看记录|tracker list|面试列表)", "tracker", "list"),
    (r"(更新|修改|tracker update)", "tracker", "update"),
    (r"(统计|数据看板|stats|看板)", "tracker", "stats"),
]


def classify_intent(text: str) -> tuple[str, str] | None:
    """基于规则判断用户意图，返回 (skill_name, action)。"""
    for pattern, skill, action in _INTENT_PATTERNS:
        if re.search(pattern, text):
            return (skill, action)
    return None


def get_help_text() -> str:
    return """
📂 [b]素材库管理 (material)[/b]
  material import <路径>   导入简历/项目文档/JD
  material list            查看素材分类
  material search <关键词>  搜索素材
  material profile         生成候选人画像

📖 [b]面试准备 (prep)[/b]
  prep for <公司> <岗位>    基于素材生成定制学习材料
  prep ask <问题>          基于素材+网络回答面试问题
  prep search <关键词>      搜索互联网补充资料
  prep save-note           保存当前回答为笔记（需确认）

🎯 [b]模拟面试 (mock)[/b]
  mock start <公司> <岗位>  开始模拟面试
  mock answer <回答>        提交回答
  mock hint                请求提示
  mock end                 提前结束
  mock review              获取评估报告

📊 [b]面试追踪 (tracker)[/b]
  tracker add              添加面试记录
  tracker list             查看所有记录
  tracker update <id>      更新面试进度
  tracker stats            统计看板

❓ [b]其他[/b]
  help                     显示此帮助
  exit/quit                退出
"""
