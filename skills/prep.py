"""Skill: 面试准备 — 基于素材生成学习资料、对话问答、网络搜索"""
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
    """面试准备 Skill"""

    def __init__(self, storage: StorageManager, obsidian_connector=None):
        self.storage = storage
        self.obsidian = obsidian_connector  # ObsidianConnector 实例（可选）
        self._conversation_history: list[dict] = []
        self._current_target: str = ""

    def run(self, action: str = "", args: str = "") -> str:
        action = action or "for"
        handler = {
            "for": self._cmd_for,
            "ask": self._cmd_ask,
            "search": self._cmd_search,
            "save_note": self._cmd_save_note,
            "help": lambda: self._show_help,
        }.get(action)
        if not handler:
            return f"[red]未知 prep 命令: {action}[/red]"
        return handler(args)

    def _show_help(self):
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
        """构建候选人上下文。"""
        parts = []

        # 画像
        profile = self.storage.load_profile()
        if profile:
            parts.append("【候选人画像】")
            parts.append(f"姓名: {profile.name}")
            parts.append(f"当前职位: {profile.current_title}")
            parts.append(f"核心技能: {', '.join(profile.core_skills)}")
            parts.append(f"亮点: {'; '.join(profile.highlight_achievements)}")
            parts.append(f"需加强: {'; '.join(profile.weak_areas)}")
            parts.append("")

        # 素材摘要
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

        # Obsidian Vault 概览
        if self.obsidian:
            try:
                vault_files = self.obsidian._scan()
                parts.append(f"【Obsidian 知识库】已连接，共 {len(vault_files)} 个文件可用，使用 material search 可搜索")
                parts.append("")
            except Exception:
                pass

        return "\n".join(parts)

    def _search_web(self, query: str) -> str:
        """搜索互联网（使用 requests 模拟搜索或调用搜索 API）。"""
        try:
            import requests
            # 使用简单的 Bing 搜索模拟，实际应替换为 Tavily/SerpAPI
            # 这里用 duckduckgo 的无 API 版本
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            url = f"https://html.duckduckgo.com/html/?q={query}"
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                # 简单提取文本片段
                import re
                snippets = re.findall(r'<a rel="nofollow" class="result__a" href="([^"]+)">(.*?)</a>', resp.text)
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

    # ─── prep for ────────────────────────────────────────

    def _cmd_for(self, args: str) -> str:
        """生成定制学习材料。"""
        if not args.strip():
            return "[red]请输入目标公司+岗位，如: prep for 字节跳动 B端产品经理[/red]"

        self._current_target = args.strip()
        profile = self.storage.load_profile()
        if not profile:
            return "[yellow]尚未生成候选人画像，建议先导入素材并执行 material profile[/yellow]"

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

    # ─── prep ask ────────────────────────────────────────

    def _cmd_ask(self, args: str) -> str:
        """基于素材回答问题。"""
        if not args.strip():
            return "[red]请输入你的问题[/red]"

        context = self._build_context()
        profile = self.storage.load_profile()

        system_template = Path(__file__).parent.parent / "prompts" / "prep_assistant.txt"
        system = system_template.read_text() if system_template.exists() else """
你是B端产品面试准备助手。回答要求：
1. 基于候选人真实素材回答
2. 先分析问题考察什么
3. 给出答题框架和思路
4. 指出可以用哪个项目经历论证
5. 不要替写完整答案，要引导
"""

        system = system.replace("{profile_summary}", context[:5000])
        system = system.replace("{material_summary}", context[:5000])
        system = system.replace("{search_results}", "")

        self._conversation_history.append({"role": "user", "content": args})

        try:
            resp = chat(
                system=system,
                messages=self._conversation_history[-10:],  # 保留最近 10 轮
                temperature=0.5,
            )
        except Exception as e:
            return f"[red]回答失败: {e}[/red]"

        self._conversation_history.append({"role": "assistant", "content": resp})
        console.print(Panel(Markdown(resp), title=f"💡 回答", border_style="green"))
        return ""

    # ─── prep search ─────────────────────────────────────

    def _cmd_search(self, args: str) -> str:
        """搜索互联网补充资料。"""
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

    # ─── prep save-note ──────────────────────────────────

    def _cmd_save_note(self, args: str = "") -> str:
        """保存最近一条回答为笔记（需要用户确认）。"""
        if not self._conversation_history:
            return "[yellow]当前没有可保存的对话内容[/yellow]"

        # 取最近一条问答
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

        # 注意：这里需要用户通过交互输入 yes/no
        # 由于是 CLI 同步模式，用户可以直接输入 yes 或 no
        # 我们在主循环中处理确认逻辑
        print("\n[请输入 yes 确认保存，或 no 取消]")

        # 先标记，让主循环处理
        self._pending_note = NoteInfo(
            title=f"面试准备笔记 {datetime.now().strftime('%m/%d %H:%M')}",
            content=note_content,
            source="prep_skill",
            tags=["面试准备"],
            created_at=datetime.now().isoformat(),
        )
        return "__CONFIRM_NEEDED__"  # 特殊标记，主循环识别

    def confirm_save_note(self) -> str:
        """确认保存笔记。"""
        if hasattr(self, '_pending_note') and self._pending_note:
            self.storage.save_note(self._pending_note)
            self._pending_note = None
            return "[green]✓ 笔记已保存[/green]"
        return "[yellow]没有待保存的笔记[/yellow]"
