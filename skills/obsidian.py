"""Skill: Obsidian Vault — 搜索、浏览、导入素材"""
from __future__ import annotations
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from core.storage import StorageManager
from connectors.obsidian import ObsidianConnector

console = Console()


class ObsidianSkill:
    """Obsidian Vault Skill"""

    def __init__(self, vault_path: str, storage: StorageManager):
        self.connector = ObsidianConnector(vault_path, storage)

    def run(self, action: str = "", args: str = "") -> str:
        handler = {
            "scan": self._cmd_scan,
            "tree": self._cmd_tree,
            "search": self._cmd_search,
            "read": self._cmd_read,
            "import": self._cmd_import,
            "help": lambda: self._show_help,
        }.get(action)
        if not handler:
            return f"[red]未知 obsidian 命令: {action}[/red]"
        return handler(args)

    def _show_help(self):
        console.print(Panel(
            "[bold]Obsidian Vault 命令:[/bold]\n"
            "  obsidian scan               重建 Vault 索引\n"
            "  obsidian tree               查看 Vault 目录结构\n"
            "  obsidian search <关键词>     全文搜索 Vault 素材\n"
            "  obsidian read <序号>        预览搜索结果中的文件\n"
            "  obsidian import <序号>      将文件导入 Agent 素材库\n"
            "  obsidian help               显示此帮助",
            title="📒 obsidian",
            border_style="blue",
        ))

    def _cmd_scan(self, args: str = "") -> str:
        """强制重建索引。"""
        self.connector.refresh_index()
        return "[green]✓ Vault 索引已更新[/green]"

    def _cmd_tree(self, args: str = "") -> str:
        """展示目录结构。"""
        self.connector.display_tree()
        return ""

    def _cmd_search(self, args: str) -> str:
        """搜索 Vault 内容。"""
        keyword = args.strip()
        if not keyword:
            return "[red]请输入搜索关键词[/red]"

        console.print(f"[dim]正在搜索: {keyword}...[/dim]")
        results = self.connector.search(keyword)

        # 保存结果供后续 read/import 使用
        self._last_results = results
        self.connector.display_results(results, keyword)

        if results:
            console.print(
                "\n[dim]使用 [bold]obsidian read <序号>[/bold] 预览，"
                "[bold]obsidian import <序号>[/bold] 导入素材库[/dim]"
            )
        return ""

    def _cmd_read(self, args: str) -> str:
        """预览搜索结果中的文件。"""
        if not hasattr(self, "_last_results") or not self._last_results:
            return "[yellow]请先执行 obsidian search <关键词>[/yellow]"

        idx = self._parse_index(args)
        if idx is None or idx < 0 or idx >= len(self._last_results):
            return f"[red]序号无效，有效范围: 1-{len(self._last_results)}[/red]"

        f = self._last_results[idx]
        content = self.connector.read_file(f["path"], max_chars=3000)
        if not content:
            return "[red]文件读取失败[/red]"

        console.print(Panel(
            Markdown(content[:2000]) if f["ext"] == ".md" else content[:2000],
            title=f"📖 {f['name']}  [dim]{f['dir']}[/dim]",
            border_style="blue",
        ))
        return ""

    def _cmd_import(self, args: str) -> str:
        """将文件导入素材库。"""
        if not hasattr(self, "_last_results") or not self._last_results:
            return "[yellow]请先执行 obsidian search <关键词>[/yellow]"

        parts = args.strip().split()
        if not parts:
            return "[red]格式: obsidian import <序号> [序号...]，如: obsidian import 1 3 5[/red]"

        indices = []
        for p in parts:
            idx = self._parse_index(p)
            if idx is not None and 0 <= idx < len(self._last_results):
                indices.append(idx)
            else:
                console.print(f"[red]跳过无效序号: {p}[/red]")

        if not indices:
            return "[yellow]未选中有效文件[/yellow]"

        results = []
        for i, idx in enumerate(indices, 1):
            f = self._last_results[idx]
            console.print(f"[{i}/{len(indices)}] 正在导入: [bold]{f['name']}[/bold]")
            result = self.connector.import_to_material(f["path"])
            results.append(result)
            console.print(result)

        return f"\n[green]✓ 已导入 {len(indices)} 个文件到素材库[/green]"

    def _parse_index(self, s: str) -> int | None:
        """解析用户输入的序号（1-based → 0-based）。"""
        s = s.strip()
        if s.isdigit():
            return int(s) - 1
        return None
