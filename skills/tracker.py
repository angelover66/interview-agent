"""Skill: 面试追踪 — 记录、更新、统计"""
from __future__ import annotations
from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
from rich.layout import Layout

from core.storage import StorageManager
from core.models import InterviewRecord

console = Console()


class TrackerSkill:
    """面试追踪 Skill"""

    def __init__(self, storage: StorageManager):
        self.storage = storage

    def run(self, action: str = "", args: str = "") -> str:
        handler = {
            "add": self._cmd_add,
            "list": self._cmd_list,
            "update": self._cmd_update,
            "stats": self._cmd_stats,
            "help": lambda: self._show_help,
        }.get(action)
        if not handler:
            return f"[red]未知 tracker 命令: {action}[/red]"
        return handler(args)

    def _show_help(self):
        console.print(Panel(
            "[bold]面试追踪命令:[/bold]\n"
            "  tracker add              添加面试记录\n"
            "  tracker list             查看所有记录\n"
            "  tracker update <id>      更新面试进度\n"
            "  tracker stats            统计看板\n"
            "  tracker help             显示此帮助",
            title="📊 tracker",
            border_style="magenta",
        ))

    # ─── add ────────────────────────────────────────────

    def _cmd_add(self, args: str = "") -> str:
        """交互式添加面试记录。"""
        console.print("[bold]📝 添加面试记录[/bold]")
        console.print("[dim]请逐项填写以下信息，直接回车可跳过可选字段[/dim]\n")

        try:
            record = InterviewRecord(
                company=input("  公司: ").strip(),
                position=input("  岗位: ").strip(),
                interview_date=input("  面试日期 (如 2026-05-10): ").strip(),
                round=input("  面试轮次 (一面/二面/三面/HR面): ").strip() or "一面",
                status=input("  当前状态 (待面试/已面试/有结果): ").strip() or "待面试",
                experience=input("  面经记录 (可选): ").strip(),
                result=input("  面试结果 (通过/挂/待定/offer/空): ").strip(),
                notes=input("  备注 (可选): ").strip(),
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
            )
        except (EOFError, KeyboardInterrupt):
            return "\n[yellow]已取消[/yellow]"

        if not record.company or not record.position:
            return "[red]公司和岗位为必填项[/red]"

        records = self.storage.load_interviews()
        record_id = len(records) + 1
        entry = {"id": record_id, **record.to_dict()}
        records.append(entry)
        self.storage.save_interviews(records)

        return f"[green]✓ 已添加面试记录: {record.company} {record.position} ({record.round})[/green]"

    # ─── list ───────────────────────────────────────────

    def _cmd_list(self, args: str = "") -> str:
        """查看所有记录。"""
        records = self.storage.load_interviews()
        if not records:
            return "[yellow]暂无面试记录。使用 tracker add 添加。[/yellow]"

        table = Table(title=f"面试记录 ({len(records)} 条)", box=box.SIMPLE)
        table.add_column("ID", style="dim", width=4)
        table.add_column("公司", style="cyan")
        table.add_column("岗位")
        table.add_column("轮次", width=8)
        table.add_column("状态", width=8)
        table.add_column("结果", width=6)
        table.add_column("面试日期")

        status_colors = {"待面试": "yellow", "已面试": "blue", "有结果": "green"}
        result_colors = {"通过": "green", "offer": "green", "挂": "red", "待定": "yellow"}

        for r in records[-20:]:  # 显示最近 20 条
            status_color = status_colors.get(r.get("status", ""), "white")
            result_color = result_colors.get(r.get("result", ""), "white")
            table.add_row(
                str(r.get("id", "")),
                r.get("company", ""),
                r.get("position", ""),
                r.get("round", ""),
                f"[{status_color}]{r.get('status', '')}[/{status_color}]",
                f"[{result_color}]{r.get('result', '')}[/{result_color}]",
                r.get("interview_date", ""),
            )

        console.print(table)
        return ""

    # ─── update ─────────────────────────────────────────

    def _cmd_update(self, args: str) -> str:
        """更新指定面试记录。"""
        record_id = args.strip()
        if not record_id or not record_id.isdigit():
            return "[red]格式: tracker update <id>[/red]"

        records = self.storage.load_interviews()
        target = None
        for r in records:
            if str(r.get("id")) == record_id:
                target = r
                break

        if not target:
            return f"[red]未找到 ID 为 {record_id} 的记录[/red]"

        console.print(f"[bold]更新记录: {target.get('company')} {target.get('position')}[/bold]")
        console.print("[dim]直接回车保持原值不变[/dim]\n")

        try:
            new_round = input(f"  轮次 [{target.get('round')}]: ").strip()
            new_status = input(f"  状态 [{target.get('status')}]: ").strip()
            new_result = input(f"  结果 [{target.get('result')}]: ").strip()
            new_experience = input(f"  面经 (可选): ").strip()
            new_notes = input(f"  备注 (可选): ").strip()
        except (EOFError, KeyboardInterrupt):
            return "\n[yellow]已取消[/yellow]"

        if new_round: target["round"] = new_round
        if new_status: target["status"] = new_status
        if new_result: target["result"] = new_result
        if new_experience: target["experience"] = new_experience
        if new_notes: target["notes"] = new_notes
        target["updated_at"] = datetime.now().isoformat()

        self.storage.save_interviews(records)
        return f"[green]✓ 已更新记录 #{record_id}[/green]"

    # ─── stats ──────────────────────────────────────────

    def _cmd_stats(self, args: str = "") -> str:
        """统计看板。"""
        records = self.storage.load_interviews()
        if not records:
            return "[yellow]暂无面试记录，添加记录后即可查看统计。[/yellow]"

        total = len(records)
        interviewed = [r for r in records if r.get("status") in ("已面试", "有结果")]
        pending = [r for r in records if r.get("status") == "待面试"]
        passed = [r for r in records if r.get("result") in ("通过", "offer")]
        failed = [r for r in records if r.get("result") == "挂"]
        pending_result = [r for r in records if r.get("result") == "待定"]

        # 轮次统计
        rounds = {}
        for r in records:
            rnd = r.get("round", "未知")
            rounds[rnd] = rounds.get(rnd, 0) + 1

        # 公司统计
        companies = {}
        for r in records:
            c = r.get("company", "未知")
            companies[c] = companies.get(c, 0) + 1

        console.print(Panel(f"""
[bold]📊 面试统计看板[/bold]

[bold]总体数据:[/bold]
  总记录: {total}
  待面试: {len(pending)}
  已完成面试: {len(interviewed)}
  通过/Offer: {len(passed)}
  已挂: {len(failed)}
  待定: {len(pending_result)}

[bold]面试转化率:[/bold]
  初面→通过: {f"{(len(passed)/(len(interviewed) or 1)*100):.0f}%" if interviewed else "N/A"}
  通过率: {f"{(len(passed)/((len(passed)+len(failed)) or 1)*100):.0f}%" if passed or failed else "N/A"}

[bold]轮次分布:[/bold]
{chr(10).join(f'  {k}: {v} 次' for k, v in sorted(rounds.items()))}

[bold]投递公司:[/bold]
{chr(10).join(f'  {c}: {n} 次' for c, n in sorted(companies.items(), key=lambda x: -x[1]))}
        """.strip(), title="📈 面试统计", border_style="magenta"))

        return ""
