"""Skill: 模拟面试 — 角色扮演、逐题问答、评估反馈"""
from __future__ import annotations
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table
from rich import box
from rich.layout import Layout
from rich.live import Live
from rich.text import Text

from core.llm import chat, chat_json
from core.storage import StorageManager
from core.models import MockSession, MockQuestion, MockAnswer

console = Console()


class MockSkill:
    """模拟面试 Skill"""

    def __init__(self, storage: StorageManager):
        self.storage = storage
        self._prompt_cache = {}
        self.current_session: MockSession | None = None

    def _load_prompt(self, name: str) -> str:
        if name not in self._prompt_cache:
            path = Path(__file__).parent.parent / "prompts" / name
            if path.exists():
                self._prompt_cache[name] = path.read_text()
            else:
                self._prompt_cache[name] = ""
        return self._prompt_cache[name]

    def run(self, action: str = "", args: str = "") -> str:
        handler = {
            "start": self._cmd_start,
            "answer": self._cmd_answer,
            "hint": self._cmd_hint,
            "end": self._cmd_end,
            "review": self._cmd_review,
            "help": lambda: self._show_help,
        }.get(action)
        if not handler:
            return f"[red]未知 mock 命令: {action}[/red]"
        return handler(args)

    def _show_help(self):
        console.print(Panel(
            "[bold]模拟面试命令:[/bold]\n"
            "  mock start <公司> <岗位>  开始模拟面试\n"
            "  mock answer <回答>        提交回答\n"
            "  mock hint                请求提示\n"
            "  mock end                 提前结束\n"
            "  mock review              获取评估报告\n"
            "  mock help                显示此帮助",
            title="🎯 mock",
            border_style="red",
        ))

    def _build_interviewer_context(self) -> str:
        """构建面试官角色上下文。"""
        profile = self.storage.load_profile()
        profile_summary = ""
        if profile:
            profile_summary = (
                f"姓名: {profile.name}\n"
                f"当前职位: {profile.current_title}\n"
                f"经验年限: {profile.years_of_experience}\n"
                f"核心技能: {', '.join(profile.core_skills)}\n"
                f"亮点: {'; '.join(profile.highlight_achievements)}\n"
                f"弱点: {'; '.join(profile.weak_areas)}\n"
                f"项目经验:\n" + "\n".join(
                    f"  - {p['name']} ({p.get('role','')}): {'; '.join(p.get('metrics',[]))}"
                    for p in (profile.key_projects or [])
                )
            )

        # 查找 JD
        jd_context = ""
        index = self.storage.get_index()
        for jd_entry in index.get("jds", []):
            try:
                jd_path = jd_entry.get("path", "")
                if jd_path:
                    content = Path(jd_path).read_text(encoding="utf-8", errors="replace")
                    jd_context += f"\n{content[:3000]}"
            except Exception:
                continue

        prompt = self._load_prompt("interviewer.txt")
        prompt = prompt.replace("{company}", self.current_session.company)
        prompt = prompt.replace("{position}", self.current_session.position)
        prompt = prompt.replace("{industry}", "互联网/B端 SaaS")
        prompt = prompt.replace("{requirements}", jd_context[:1500] or "标准 B 端产品经理要求")
        prompt = prompt.replace("{profile_summary}", profile_summary[:2000])

        return prompt

    # ─── start ──────────────────────────────────────────

    def _cmd_start(self, args: str) -> str:
        """开始模拟面试。"""
        parts = args.strip().split(maxsplit=1)
        if len(parts) < 2:
            return "[red]格式: mock start <公司> <岗位>，如: mock start 字节跳动 飞书B端产品经理[/red]"

        self.current_session = MockSession(
            company=parts[0],
            position=parts[1],
            started_at=datetime.now().isoformat(),
        )

        console.print(f"\n[bold]🎯 开始模拟面试: {parts[0]} — {parts[1]}[/bold]")
        console.print("[dim]面试即将开始，面试官会先做自我介绍并说明流程。[/dim]\n")

        # 构建面试官 context 并生成开场 + 第一题
        system = self._build_interviewer_context()
        if not system:
            return "[red]面试官角色加载失败[/red]"

        # 对话历史：面试官就是 assistant
        self._interview_messages = []

        try:
            resp = chat(
                system=system,
                messages=[],
                temperature=0.7,
                max_tokens=2000,
            )
        except Exception as e:
            return f"[red]面试启动失败: {e}[/red]"

        self._interview_messages.append({"role": "assistant", "content": resp})
        console.print(Panel(Markdown(resp), title=f"🎙️ {parts[0]} 面试官", border_style="red"))

        # 尝试从回复中提取问题
        self.current_session.questions.append(MockQuestion(
            question=resp,
            type="综合",
        ))

        return ""

    # ─── answer ─────────────────────────────────────────

    def _cmd_answer(self, args: str) -> str:
        """提交回答，面试官追问或出下一题。"""
        if not self.current_session:
            return "[red]未开始面试。使用 mock start <公司> <岗位> 开始。[/red]"

        answer_text = args.strip()
        if not answer_text:
            return "[red]请输入你的回答[/red]"

        # 保存回答
        current_q = self.current_session.questions[-1].question if self.current_session.questions else ""
        answer_record = MockAnswer(question=current_q, answer=answer_text)
        self.current_session.answers.append(answer_record)

        # 生成面试官回应
        self._interview_messages.append({"role": "user", "content": answer_text})

        system = self._build_interviewer_context()

        try:
            resp = chat(
                system=system,
                messages=self._interview_messages,
                temperature=0.7,
                max_tokens=2000,
            )
        except Exception as e:
            return f"[red]回复生成失败: {e}[/red]"

        self._interview_messages.append({"role": "assistant", "content": resp})
        self.current_session.questions.append(MockQuestion(question=resp, type="综合"))

        console.print(Panel(Markdown(resp), title=f"🎙️ 面试官", border_style="red"))

        # 检查是否超过最大题数
        max_q = 10
        if len(self.current_session.answers) >= max_q:
            console.print(f"\n[bold yellow]已达最大题数 ({max_q})，面试自动结束。输入 mock review 查看评估。[/bold yellow]")
            self.current_session.status = "已完成"
            self.current_session.ended_at = datetime.now().isoformat()
            self.storage.save_session(self.current_session)

        return ""

    # ─── hint ───────────────────────────────────────────

    def _cmd_hint(self, args: str = "") -> str:
        """请求当前问题的提示。"""
        if not self.current_session:
            return "[red]未开始面试[/red]"

        if not self.current_session.questions:
            return "[yellow]当前没有问题[/yellow]"

        last_q = self.current_session.questions[-1].question

        system = """你是面试教练。给候选人提供当前面试问题的答题提示。

要求：
1. 不要直接给答案
2. 给思考框架（如 STAR、金字塔原理、MECE）
3. 点出 2-3 个切入角度
4. 提示哪些项目经历可以用
5. 控制在 100 字以内"""

        try:
            resp = chat(system=system, messages=[
                {"role": "user", "content": f"面试问题：{last_q}\n\n请给出答题提示。不要直接给答案，给框架和思路。"}
            ], temperature=0.5, max_tokens=500)
        except Exception as e:
            return f"[red]提示生成失败: {e}[/red]"

        console.print(Panel(Markdown(resp), title="💡 答题提示", border_style="yellow"))
        return ""

    # ─── end ────────────────────────────────────────────

    def _cmd_end(self, args: str = "") -> str:
        """提前结束面试。"""
        if not self.current_session:
            return "[red]未开始面试[/red]"

        self.current_session.status = "已完成"
        self.current_session.ended_at = datetime.now().isoformat()
        self.storage.save_session(self.current_session)

        console.print(f"[bold yellow]面试已结束。共回答 {len(self.current_session.answers)} 题。[/bold yellow]")
        console.print("[dim]输入 mock review 查看评估报告。[/dim]")
        return ""

    # ─── review ─────────────────────────────────────────

    def _cmd_review(self, args: str = "") -> str:
        """生成评估报告。"""
        if not self.current_session:
            # 查找最近的已完成面试
            sessions = self.storage.list_sessions()
            if not sessions:
                return "[red]没有可评估的面试记录。请先完成一次模拟面试。[/red]"
            last = sessions[0]
            if last["status"] != "已完成":
                return "[red]最近的面试尚未完成，请先结束面试 (mock end)[/red]"
            self.current_session = MockSession(**last)

        if self.current_session.status != "已完成":
            return "[red]面试尚未完成，请先结束面试 (mock end)[/red]"

        if not self.current_session.answers:
            return "[red]没有回答记录，无法评估[/red]"

        console.print("[dim]正在生成评估报告...[/dim]")

        # 构建面试记录文本
        transcript_lines = []
        for i, (q, a) in enumerate(zip(self.current_session.questions, self.current_session.answers)):
            transcript_lines.append(f"Q{i+1}: {q.question[:200]}")
            transcript_lines.append(f"A{i+1}: {a.answer[:1000]}")
            transcript_lines.append("")

        transcript = "\n".join(transcript_lines)

        # 获取画像
        profile = self.storage.load_profile()
        profile_summary = ""
        if profile:
            profile_summary = f"{profile.name}, {profile.current_title}, 核心技能: {', '.join(profile.core_skills[:5])}"

        # 加载评估 prompt
        eval_prompt = self._load_prompt("evaluator.txt")
        eval_prompt = eval_prompt.replace("{position}", self.current_session.position)
        eval_prompt = eval_prompt.replace("{company}", self.current_session.company)
        eval_prompt = eval_prompt.replace("{profile_summary}", profile_summary[:1000])
        eval_prompt = eval_prompt.replace("{transcript}", transcript[:15000])

        try:
            result = chat_json(system=eval_prompt, messages=[
                {"role": "user", "content": "请评估上述面试表现"}
            ], temperature=0.3)
        except Exception as e:
            return f"[red]评估失败: {e}[/red]"

        self.current_session.overall_score = result.get("overall_score", 0)
        self.current_session.dimension_scores = result.get("dimension_scores", {})
        self.current_session.summary = result.get("summary", "")

        # 保存
        self.storage.save_session(self.current_session)

        # 展示报告
        console.print(f"\n[bold]📊 面试评估报告[/bold]")
        console.print(f"[bold]公司:[/bold] {self.current_session.company}  [bold]岗位:[/bold] {self.current_session.position}")
        console.print(f"[bold]回答题数:[/bold] {len(self.current_session.answers)}")
        console.print(f"")

        # 总分
        score = result.get("overall_score", 0)
        score_color = "green" if score >= 7 else "yellow" if score >= 5 else "red"
        console.print(f"[bold {score_color}]总分: {score}/10[/bold {score_color}]")

        # 维度评分
        table = Table(box=box.SIMPLE)
        table.add_column("维度", style="cyan")
        table.add_column("评分", justify="center")
        table.add_column("等级")

        dims = result.get("dimension_scores", {})
        for dim, s in sorted(dims.items(), key=lambda x: x[1]):
            level = "★" * max(1, round(s / 3)) + "☆" * (3 - max(1, round(s / 3)))
            color = "green" if s >= 7 else "yellow" if s >= 5 else "red"
            table.add_row(dim, f"[{color}]{s}/10[/{color}]", level)
        console.print(table)

        # 优势与不足
        console.print(f"\n[bold green]优势:[/bold green]")
        for s in result.get("strengths", []):
            console.print(f"  ✓ {s}")

        console.print(f"\n[bold red]待改进:[/bold red]")
        for w in result.get("weaknesses", []):
            console.print(f"  ✗ {w}")

        # 改进建议
        console.print(f"\n[bold]优先级改进建议:[/bold]")
        for imp in result.get("priority_improvements", []):
            priority_tag = {"高": "[red]高[/red]", "中": "[yellow]中[/yellow]", "低": "[dim]低[/dim]"}.get(imp.get("priority", "中"), "[dim]中[/dim]")
            console.print(f"  [{priority_tag}] [bold]{imp.get('area')}[/bold]: {imp.get('suggestion')}")

        # 示范回答
        sample = result.get("sample_answer", "")
        if sample:
            console.print(f"\n[bold]💡 示范回答（针对薄弱项）:[/bold]")
            console.print(Panel(Markdown(sample[:1000]), border_style="blue"))

        # 总结
        console.print(f"\n[bold]总结:[/bold] {result.get('summary', '')}")
        console.print("")

        return ""
