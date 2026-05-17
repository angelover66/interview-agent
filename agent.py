#!/usr/bin/env python3
"""
Interview Agent — B 端产品经理面试助手
========================================
一个智能面试准备 Agent，支持：
  - 素材库管理（简历/项目/JD 导入归类）
  - 面试准备（定制化学习材料 + 问答）
  - 模拟面试（角色扮演 + 评分）
  - 面试追踪（记录 + 统计）

快速开始：
  python agent.py                    启动交互模式
  python agent.py material list      直接运行命令
  python agent.py mock start 字节  PM

首次使用：
  1. material import <简历文件>      导入素材
  2. material profile                生成画像
  3. prep for <公司> <岗位>         准备面试
  4. mock start <公司> <岗位>       开始模拟
"""
from __future__ import annotations
import sys
import os
from pathlib import Path

# 确保项目根目录在 path 中
sys.path.insert(0, str(Path(__file__).parent))

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt
from rich.table import Table
from rich import box
from rich.text import Text

from core.storage import StorageManager
from core.scheduler import register, get_skill, all_skills, parse_command, classify_intent, get_help_text
from skills.material import MaterialSkill
from skills.prep import PrepSkill
from skills.mock import MockSkill
from skills.obsidian import ObsidianSkill

console = Console()

# ─── Banner ────────────────────────────────────────────

BANNER = """
╔══════════════════════════════════════════════════╗
║         🎯  B端产品经理面试助手  v1.0            ║
║     ───────────────────────────────────────      ║
║     素材库 · 面试准备 · 模拟面试 · 追踪         ║
╚══════════════════════════════════════════════════╝
"""


def print_banner():
    console.print(BANNER, style="bold cyan", justify="center")
    console.print("输入 [bold]help[/bold] 查看所有命令，[bold]exit[/bold] 退出\n", justify="center")


# ─── 命令路由 ─────────────────────────────────────────

class AgentApp:
    """Agent 主应用"""

    def __init__(self):
        self.storage = StorageManager(base_dir="./data")

        # 读取 Obsidian Vault 配置
        import yaml
        config_path = Path(__file__).parent / "config.yaml"
        config = yaml.safe_load(config_path.read_text()) if config_path.exists() else {}
        vault_path = config.get("obsidian", {}).get("vault_path", "")

        # 初始化 Obsidian 连接器
        obsidian_connector = None
        if vault_path:
            from connectors.obsidian import ObsidianConnector
            obsidian_connector = ObsidianConnector(vault_path, self.storage)

        # 初始化并注册 Skills（传入 obsidian 连接器）
        self.material = MaterialSkill(self.storage, obsidian_connector)
        self.prep = PrepSkill(self.storage, obsidian_connector)
        self.mock = MockSkill(self.storage)

        if obsidian_connector:
            self.obsidian = ObsidianSkill(vault_path, self.storage)
            register("obsidian", self.obsidian)

        register("material", self.material)
        register("prep", self.prep)
        register("mock", self.mock)
        register("obsidian", self.obsidian)

        # 未完成的多轮上下文
        self._context: dict = {}

    def route(self, user_input: str) -> str | None:
        """
        解析用户输入并路由到对应 Skill。
        返回输出文本，None 表示退出。
        """
        text = user_input.strip()

        # 退出
        if text.lower() in ("exit", "quit", "退出"):
            return None

        # 帮助
        if text.lower() in ("help", "h", "?"):
            return get_help_text()

        # 尝试解析为显式命令: material xxx, prep xxx 等
        cmd = parse_command(text)
        if cmd:
            skill_name, args = cmd
            return self._exec_skill(skill_name, args)

        # 如果是在模拟面试中状态，默认走 mock answer
        if self.mock.current_session and self.mock.current_session.status == "进行中":
            return self._exec_skill("mock", f"answer {text}")

        # 如果是在 prep 对话中，默认走 prep ask
        if self.prep._conversation_history:
            # 最近有 prep 对话，默认为 prep ask
            return self._exec_skill("prep", f"ask {text}")

        # 尝试自然语言意图识别
        intent = classify_intent(text)
        if intent:
            skill_name, action = intent
            return self._exec_skill(skill_name, f"{action} {text}")

        # 默认：当作 prep ask（面试问答模式）
        return self._exec_skill("prep", f"ask {text}")

    def _exec_skill(self, skill_name: str, args: str) -> str:
        """执行 skill 命令并解析 args。"""
        skill = get_skill(skill_name)
        if not skill:
            return f"[red]未知技能: {skill_name}[/red]。输入 help 查看可用命令。"

        # 分割 action 和剩余参数
        args = args.strip()
        parts = args.split(maxsplit=1)
        action = parts[0] if parts else "help"
        rest = parts[1] if len(parts) > 1 else ""

        # 特殊处理：如果 action 是数字或空，设默认
        if action.isdigit() or not action:
            action = "help"
            rest = args

        result = skill.run(action, rest)
        return result or ""

    def run_interactive(self):
        """交互式主循环。"""
        print_banner()

        while True:
            try:
                user_input = Prompt.ask("\n[bold cyan]你[/bold cyan]")
            except (EOFError, KeyboardInterrupt):
                console.print("\n\n[yellow]再见，祝你面试顺利！[/yellow]")
                break

            if not user_input or not user_input.strip():
                continue

            try:
                output = self.route(user_input)

                # 处理特殊标记
                if output == "__CONFIRM_NEEDED__":
                    confirm = Prompt.ask("[yellow]是否保存此内容为笔记？[/yellow]", choices=["yes", "no"], default="no")
                    if confirm == "yes":
                        result = self.prep.confirm_save_note()
                        console.print(result)
                    else:
                        console.print("[dim]已取消保存[/dim]")
                    continue

                if output is None:
                    console.print("\n[bold]再见，祝你面试顺利！[/bold]")
                    break

                # 如果 output 为空（skill 内部已打印），不重复输出
                if output:
                    console.print(output)

            except KeyboardInterrupt:
                console.print("\n[yellow]操作已取消[/yellow]")
                continue
            except Exception as e:
                console.print(f"\n[red]出错了: {e}[/red]")
                import traceback
                if "--debug" in sys.argv:
                    console.print(traceback.format_exc())
                continue


def run_once(args: list[str]):
    """单次命令模式。"""
    app = AgentApp()
    cmd = " ".join(args)
    output = app.route(cmd)
    if output is None:
        return
    if output:
        console.print(output)


def main():
    if len(sys.argv) > 1:
        run_once(sys.argv[1:])
    else:
        app = AgentApp()
        app.run_interactive()


if __name__ == "__main__":
    main()
