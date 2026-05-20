"""Skill: 面试准备 — 基于素材生成学习资料、对话问答、网络搜索

═══════════════════════════════════════════════════════════════════════════════
架构设计说明（AI 产品经理视角）
═══════════════════════════════════════════════════════════════════════════════

一、模块职责

PrepSkill 是面试准备的「知识引擎」，负责三个核心能力：
  1. prep for — 基于候选人素材 + 目标岗位，生成定制面试学习材料
  2. prep ask — 面试问答模式，基于素材回答问题，引导答题思路
  3. prep search — 互联网搜索补充资料

与 MockSkill 的区别：
  - PrepSkill：学习模式，帮助候选人理解和准备面试题
  - MockSkill：考试模式，模拟真实面试的问答节奏和压力
  - PrepSkill 可以追问、讨论，MockSkill 是严格的一题一答

二、对话历史管理

_conversation_history 记录当前 prep 会话的所有问答轮次，
作用：
  1. 提供对话上下文（LLM 可以看到之前的问答）
  2. prep save-note 时从中提取最近的内容保存为笔记
  3. route() 中判断是否在 prep 对话状态（有历史记录 = 在对话中）

对话保留最近 10 轮（通过 messages[-10:] 截断），
防止 context 窗口溢出，同时保证足够的上文信息。

三、互联网搜索策略

_search_web() 使用 DuckDuckGo 的 HTML 版（非 JS 版），
不需要 API Key，但返回质量和稳定性不如付费 API。

为什么选 DuckDuckGo：
  - 零成本，不需要注册 API Key
  - 个人使用量低，不会触发频率限制
  - 搜索结果对中文支持尚可

已知局限：
  - 页面结构可能变化（HTML 版不受影响，但未来可能被关闭）
  - 不支持图片、视频、社交媒体搜索
  - 如果 DuckDuckGo 不可用，可以切换到 Tavily/SerpAPI

四、生成材料的 prompt 策略

prep for 的 system prompt 要求 LLM 输出五个维度：
  1. 岗位核心要求分析 — 帮助候选人理解 JD 背后真正看重什么
  2. 匹配度分析 — 哪些经历可以用，哪些是短板（诚实评估）
  3. 高频面试题预测 — 5-8 个可能有价值的问题
  4. 准备建议 — 针对薄弱项的具体提升方向
  5. 推荐复习知识点 — 知识点而非答题技巧

这五个维度覆盖了「知己（匹配度）→知彼（JD分析）→备战（预测+建议+知识点）」
的完整准备链路。

五、笔记保存的异步确认机制

prep save-note 不是直接保存，而是先标记 _pending_note 状态，
返回 "__CONFIRM_NEEDED__" 给主循环，由主循环二次确认后再写入。

为什么需要二次确认：
  - 避免误操作：LLM 的回答可能涉及个人隐私
  - 给用户取消的机会：按了 save 才发现内容不对
  - CLI 模式下用户需要输入 yes/no，这需要主循环的支持
═══════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from core.llm import chat, chat_json
from core.storage import StorageManager
from core.models import NoteInfo

console = Console()


class PrepSkill:
    """面试准备 Skill — 基于候选人素材做定制化面试准备。

    三大核心命令：
      prep for    → 生成学习材料（一次性，覆盖写入）
      prep ask    → 对话式问答（多轮，有上下文记忆）
      prep search → 搜索互联网补充资料（无状态）

    对外接口：
      run("for", "字节跳动 B端PM")  → 生成学习材料
      run("ask", "什么是PLG策略？")  → 对话问答
      run("search", "飞书产品分析")   → 网络搜索
      run("save_note")               → 保存笔记（需确认）
    """

    def __init__(self, storage: StorageManager, obsidian_connector=None):
        """初始化面试准备 Skill。

        Args:
            storage: StorageManager 实例
            obsidian_connector: ObsidianConnector 实例（可选），用于搜索知识库
        """
        self.storage = storage
        self.obsidian = obsidian_connector
        self._conversation_history: list[dict] = []  # 对话历史 [{role, content}]
        self._current_target: str = ""               # 当前准备的目标岗位

    def run(self, action: str = "", args: str = "") -> str:
        """统一路由入口，根据 action 分发到对应私有方法。"""
        action = action or "for"
        handler = {
            "for": self._cmd_for,          # 生成学习材料
            "ask": self._cmd_ask,          # 对话问答
            "search": self._cmd_search,    # 网络搜索
            "save_note": self._cmd_save_note,  # 保存笔记
            "help": lambda: self._show_help,
        }.get(action)
        if not handler:
            return f"[red]未知 prep 命令: {action}[/red]"
        return handler(args)

    def _show_help(self):
        """显示 prep 命令的帮助信息。"""
        console.print(Panel(
            "[bold]面试准备命令:[/bold]\n"
            "  prep for <公司> <岗位>    基于素材生成定制学习材料\n"
            "  prep ask <问题>          基于素材+网络回答面试问题\n"
            "  prep search <关键词>      搜索互联网补充资料\n"
            "  prep save-note           保存当前回答为笔记（需确认）\n"
            "  prep help                显示此帮助",
            title="📖 prep",
            border_style="green",
        ))

    def _build_context(self) -> str:
        """构建候选人上下文文本，拼接素材摘要 + Obsidian 知识库信息。

        这个上下文会注入到 LLM 的 system prompt 中，让 LLM 了解
        候选人的背景、技能、项目经历，从而给出针对性建议。

        Returns:
            格式化的上下文文本（素材摘要 + Obsidian 概览）
        """
        parts = []

        # 素材库摘要：统计每类素材的数量和前几个标题
        index = self.storage.get_index()
        material_summary = []
        for key in ["resumes", "projects", "jds"]:
            entries = index.get(key, [])
            if entries:
                material_summary.append(f"{key}: {len(entries)} 份")
                for e in entries[:5]:
                    material_summary.append(f"  - {e.get('title', e.get('file', ''))}")
        if material_summary:
            parts.append("【素材摘要】")
            parts.extend(material_summary)
            parts.append("")

        # Obsidian Vault 概览（如果已连接）
        if self.obsidian:
            try:
                vault_files = self.obsidian._scan()
                parts.append(f"【Obsidian 知识库】已连接，共 {len(vault_files)} 个文件可用，使用 material search 可搜索")
                parts.append("")
            except Exception:
                pass

        return "\n".join(parts)

    def _search_web(self, query: str) -> str:
        """搜索互联网 — 使用 DuckDuckGo HTML 版（免费，无需 API Key）。

        搜索策略：
          1. 调用 DuckDuckGo 的 HTML 版（html.duckduckgo.com/html/），
             返回无 JS 依赖的静态页面
          2. 用正则从返回的 HTML 中提取标题、链接、摘要片段
          3. 最多返回 5 条结果

        为什么不用更专业的搜索 API：
          - Tavily/SerpAPI 需要付费和 API Key
          - 个人使用量低，免费方案够用
          - DuckDuckGo 对中文有基本支持

        Args:
            query: 搜索关键词

        Returns:
            格式化的搜索结果文本，5 条以内
        """
        try:
            import requests
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            url = f"https://html.duckduckgo.com/html/?q={query}"
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                import re
                # 提取搜索结果中的标题和链接
                snippets = re.findall(r'<a rel="nofollow" class="result__a" href="([^"]+)">(.*?)</a>', resp.text)
                # 提取搜索结果摘要
                bodies = re.findall(r'<a class="result__snippet"[^>]*>(.*?)</a>', resp.text)
                results = []
                for i, (url, title) in enumerate(snippets[:5]):
                    body = bodies[i] if i < len(bodies) else ""
                    results.append(f"{i+1}. [{title.strip()}]({url})\n   {body.strip()}")
                return "\n\n".join(results) if results else "（搜索未返回有效结果）"
            else:
                return "（搜索服务暂不可用）"
        except Exception as e:
            return f"（搜索出错: {e}）"

    # ═══════════════════════════════════════════════════════════════════════════
    # prep for — 生成定制学习材料（核心功能）
    # ═══════════════════════════════════════════════════════════════════════════

    def _cmd_for(self, args: str) -> str:
        """基于候选人素材 + 目标岗位，生成定制面试学习材料。

        输出五个维度：
          1. 岗位核心要求分析 — 这个岗位最看重什么能力
          2. 候选人匹配度分析 — 哪些经历可以用，哪些是短板
          3. 高频面试题预测 — 基于 JD 要求预测 5-8 个问题
          4. 准备建议 — 每个薄弱项的具体提升方向
          5. 推荐复习的知识点 — 知识体系而非答题技巧

        前置条件：需有简历+岗位信息（由 Web UI 传入 _file_context），
        素材库为空不影响生成。

        Args:
            args: 目标岗位描述，如 "字节跳动 B端产品经理"

        Returns:
            Rich 格式的学习材料
        """
        if not args.strip():
            return "[red]请输入目标公司+岗位，如: prep for 字节跳动 B端产品经理[/red]"

        self._current_target = args.strip()

        context = self._build_context()

        console.print(f"[dim]正在为 [bold]{args}[/bold] 生成学习材料...[/dim]")

        system = f"""你是B端产品面试教练。基于候选人的素材，为 "{args}" 这个目标岗位生成定制学习材料。

你需要输出：
1. 岗位核心要求分析（这个岗位最看重什么能力）
2. 候选人匹配度分析（哪些经历可以用，哪些是短板）
3. 高频面试题预测（基于JD要求预测 5-8 个问题）
4. 准备建议（每个薄弱项的具体提升方向）
5. 推荐复习的知识点

注意：
- 所有分析必须基于候选人真实素材，不要编造
- 如果某方面素材不足，明确指出并建议补充
- 每个预测题要说明为什么这个题重要"""

        try:
            resp = chat(system=system, messages=[
                {"role": "user", "content": f"候选人信息：\n\n{context[:20000]}"}
            ], temperature=0.5)
        except Exception as e:
            return f"[red]生成失败: {e}[/red]"

        console.print(Panel(Markdown(resp), title=f"📖 准备材料: {args}", border_style="green"))
        return ""

    # ═══════════════════════════════════════════════════════════════════════════
    # prep ask — 对话式问答
    # ═══════════════════════════════════════════════════════════════════════════

    def _cmd_ask(self, args: str) -> str:
        """基于素材回答面试相关问题，引导答题思路而非直接给答案。

        设计原则：
          - 先分析问题考察什么（帮助候选人理解面试官意图）
          - 给出答题框架和思路（STAR、金字塔、MECE 等）
          - 指出可以用哪个项目经历论证（将抽象问题映射到真实素材）
          - 不要替写完整答案（面试是候选人自己的战场）

        对话历史保留最近 10 轮，超出部分自动截断。

        Args:
            args: 问题文本

        Returns:
            Rich 格式的回答
        """
        if not args.strip():
            return "[red]请输入你的问题[/red]"

        context = self._build_context()
        profile = self.storage.load_profile()

        # 加载 prep_assistant prompt 模板
        system_template = Path(__file__).parent.parent / "prompts" / "prep_assistant.txt"
        system = system_template.read_text() if system_template.exists() else """
你是B端产品面试准备助手。回答要求：
1. 基于候选人真实素材回答
2. 先分析问题考察什么
3. 给出答题框架和思路
4. 指出可以用哪个项目经历论证
5. 不要替写完整答案，要引导
"""

        # 填充 prompt 模板中的占位符
        system = system.replace("{profile_summary}", context[:5000])
        system = system.replace("{material_summary}", context[:5000])
        system = system.replace("{search_results}", "")

        # 追加到对话历史
        self._conversation_history.append({"role": "user", "content": args})

        try:
            resp = chat(
                system=system,
                messages=self._conversation_history[-10:],  # 最近 10 轮，防 context 溢出
                temperature=0.5,
            )
        except Exception as e:
            return f"[red]回答失败: {e}[/red]"

        self._conversation_history.append({"role": "assistant", "content": resp})
        console.print(Panel(Markdown(resp), title=f"💡 回答", border_style="green"))
        return ""

    # ═══════════════════════════════════════════════════════════════════════════
    # prep search — 互联网搜索
    # ═══════════════════════════════════════════════════════════════════════════

    def _cmd_search(self, args: str) -> str:
        """搜索互联网补充资料。

        适用场景：
          - 了解目标公司的产品、业务、文化
          - 搜索行业趋势、竞品分析
          - 查找面试面经、薪资范围等公开信息

        注意：搜索结果来自公开互联网，需要候选人自行判断准确性。
        DuckDuckGo 的结果可能不如 Google 精准，尤其是中文内容。

        Args:
            args: 搜索关键词

        Returns:
            Rich 格式的搜索结果
        """
        if not args.strip():
            return "[red]请输入搜索关键词[/red]"

        console.print(f"[dim]正在搜索: {args}...[/dim]")
        results = self._search_web(args)

        console.print(Panel(
            Markdown(f"## 搜索结果: {args}\n\n{results}"),
            title="🌐 网络搜索",
            border_style="blue",
        ))
        return ""

    # ═══════════════════════════════════════════════════════════════════════════
    # prep save-note — 保存对话为笔记（需要二次确认）
    # ═══════════════════════════════════════════════════════════════════════════

    def _cmd_save_note(self, args: str = "") -> str:
        """保存最近一条问答为笔记。不直接保存，需要用户确认。

        返回 "__CONFIRM_NEEDED__" 标记，由主循环处理确认逻辑。
        这样设计的原因：
          - CLI 模式：主循环弹出 yes/no 确认
          - Web 模式：直接保存（UI 上已有确认按钮）

        Returns:
            "__CONFIRM_NEEDED__" 或错误信息
        """
        if not self._conversation_history:
            return "[yellow]当前没有可保存的对话内容[/yellow]"

        # 取最近一条问答（可能是 1 条回答或 1 对问答）
        recent = self._conversation_history[-2:] if len(self._conversation_history) >= 2 else self._conversation_history[-1:]

        note_content = "\n---\n".join(
            f"{'Q' if m['role']=='user' else 'A'}: {m['content'][:500]}"
            for m in recent
        )

        console.print(Panel(
            f"[yellow]以下内容将被保存为笔记:[/yellow]\n\n{note_content}\n\n"
            f"[bold]是否确认保存？(yes/no)[/bold] ",
            title="📝 保存笔记确认",
            border_style="yellow",
        ))

        print("\n[请输入 yes 确认保存，或 no 取消]")

        # 先标记待保存状态，由主循环处理确认
        self._pending_note = NoteInfo(
            title=f"面试准备笔记 {datetime.now().strftime('%m/%d %H:%M')}",
            content=note_content,
            source="prep_skill",
            tags=["面试准备"],
            created_at=datetime.now().isoformat(),
        )
        return "__CONFIRM_NEEDED__"

    def confirm_save_note(self) -> str:
        """确认保存笔记 — 由主循环确认后调用。

        Returns:
            保存结果
        """
        if hasattr(self, '_pending_note') and self._pending_note:
            self.storage.save_note(self._pending_note)
            self._pending_note = None
            return "[green]✓ 笔记已保存[/green]"
        return "[yellow]没有待保存的笔记[/yellow]"
