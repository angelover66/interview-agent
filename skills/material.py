"""Skill: 素材库管理 — 导入、归类、搜索、生成画像"""
from __future__ import annotations
import json
import os
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.tree import Tree
from rich import box

from core.llm import chat, chat_json
from core.storage import StorageManager
from core.models import ResumeInfo, ProjectInfo, JDInfo, NoteInfo, UserProfile
from core.scheduler import get_help_text

console = Console()


class MaterialSkill:
    """素材库管理 Skill"""

    def __init__(self, storage: StorageManager):
        self.storage = storage
        self._prompt_cache = {}

    def _load_prompt(self, name: str) -> str:
        if name not in self._prompt_cache:
            path = Path(__file__).parent.parent / "prompts" / name
            if path.exists():
                self._prompt_cache[name] = path.read_text()
            else:
                self._prompt_cache[name] = ""
        return self._prompt_cache[name]

    # ─── 公开命令 ────────────────────────────────────────

    def run(self, action: str = "", args: str = "") -> str:
        """外部统一调用入口。返回结果文本（rich 格式）。"""
        action = action or "help"
        handler = {
            "import": self._cmd_import,
            "list": self._cmd_list,
            "search": self._cmd_search,
            "profile": self._cmd_profile,
            "help": lambda: self._show_help,
        }.get(action)
        if not handler:
            return f"[red]未知 material 命令: {action}。输入 material help 查看帮助。[/red]"
        return handler(args)

    def _show_help(self):
        console.print(Panel(
            "[bold]素材库管理命令:[/bold]\n"
            "  material import <路径>    导入简历/项目文档/JD\n"
            "  material list             查看素材分类\n"
            "  material search <关键词>   搜索素材\n"
            "  material profile          生成候选人画像\n"
            "  material help             显示此帮助",
            title="📂 material",
            border_style="blue",
        ))

    # ─── import ──────────────────────────────────────────

    def _detect_file_type(self, filename: str) -> str:
        name = filename.lower()
        if any(k in name for k in ["简历", "resume", "cv"]):
            return "resume"
        if any(k in name for k in ["jd", "岗位", "职位描述", "招聘"]):
            return "jd"
        return "project"

    def _cmd_import(self, args: str) -> str:
        path = args.strip().strip('"').strip("'")
        if not path or not os.path.exists(path):
            return f"[red]文件不存在: {path}[/red]"

        # 复制到素材库
        file_type = self._detect_file_type(os.path.basename(path))
        target = self.storage.copy_file(path, file_type)
        if not target:
            return "[red]文件复制失败[/red]"

        # 读取内容
        content = Path(path).read_text(encoding="utf-8", errors="replace")[:15000]

        # 调用 LLM 提取结构
        prompt = self._load_prompt("material_extract.txt")
        try:
            result = chat_json(system=prompt, messages=[
                {"role": "user", "content": f"请提取以下{'简历' if file_type=='resume' else '项目文档' if file_type=='project' else 'JD'}信息：\n\n{content}"}
            ])
        except Exception as e:
            return f"[red]LLM 提取失败: {e}[/red]\n文件已保存到素材库，但未能自动提取结构化信息。"

        # 更新索引
        index = self.storage.get_index()
        entry = {
            "file": os.path.basename(target),
            "path": target,
            "type": result.get("type", file_type),
            "title": self._get_title(result.get("data", {})),
            "imported_at": datetime.now().isoformat(),
        }
        key_map = {"resume": "resumes", "project": "projects", "jd": "jds"}
        index.get(key_map.get(file_type, "projects"), []).append(entry)
        self.storage.save_index(index)

        data = result.get("data", {})
        summary = self._format_extract_result(file_type, data)
        return (
            f"[green]✓ 导入成功: {os.path.basename(target)}[/green]\n"
            f"[bold]类别:[/bold] {file_type}\n\n"
            f"{summary}\n\n"
            f"[dim]素材已入库，输入 material list 查看[/dim]"
        )

    def _get_title(self, data: dict) -> str:
        return data.get("name") or data.get("company", "") + " " + data.get("position", "") or data.get("title", "")

    def _format_extract_result(self, file_type: str, data: dict) -> str:
        if file_type == "resume":
            parts = []
            if data.get("name"): parts.append(f"[bold]姓名:[/bold] {data['name']}")
            if data.get("title"): parts.append(f"[bold]职位:[/bold] {data['title']}")
            if data.get("summary"): parts.append(f"[bold]摘要:[/bold] {data['summary'][:200]}")
            if data.get("skills"): parts.append(f"[bold]核心技能:[/bold] {', '.join(data['skills'][:8])}")
            if data.get("work_experience"):
                for exp in data["work_experience"][:3]:
                    parts.append(f"  • {exp.get('company')} — {exp.get('role')}")
            return "\n".join(parts)
        elif file_type == "project":
            parts = []
            if data.get("name"): parts.append(f"[bold]项目:[/bold] {data['name']}")
            if data.get("role"): parts.append(f"[bold]角色:[/bold] {data['role']}")
            if data.get("background"): parts.append(f"[bold]背景:[/bold] {data['background'][:200]}")
            if data.get("results"):
                parts.append(f"[bold]成果:[/bold]")
                for r in data["results"][:5]:
                    parts.append(f"  • {r}")
            return "\n".join(parts)
        else:
            parts = []
            if data.get("company"): parts.append(f"[bold]公司:[/bold] {data['company']}")
            if data.get("position"): parts.append(f"[bold]岗位:[/bold] {data['position']}")
            if data.get("responsibilities"):
                parts.append(f"[bold]职责:[/bold]")
                for r in data["responsibilities"][:5]:
                    parts.append(f"  • {r}")
            if data.get("requirements"):
                parts.append(f"[bold]要求:[/bold]")
                for r in data["requirements"][:5]:
                    parts.append(f"  • {r}")
            return "\n".join(parts)

    # ─── list ────────────────────────────────────────────

    def _cmd_list(self, args: str = "") -> str:
        index = self.storage.get_index()
        files = self.storage.list_raw_files()

        tree = Tree("[bold]📂 素材库[/bold]")

        # 简历
        resumes = [f for f in files if f["category"] == "resumes"]
        if resumes:
            r_tree = tree.add(f"[bold]📄 简历 ({len(resumes)})[/bold]")
            for f in resumes:
                r_tree.add(f"{f['name']}  [dim]{f['size']//1024}KB[/dim]")

        # 项目
        projects = [f for f in files if f["category"] == "projects"]
        if projects:
            p_tree = tree.add(f"[bold]📁 项目文档 ({len(projects)})[/bold]")
            for f in projects:
                p_tree.add(f"{f['name']}  [dim]{f['size']//1024}KB[/dim]")

        # JD
        jds = [f for f in files if f["category"] == "jds"]
        if jds:
            j_tree = tree.add(f"[bold]🎯 岗位描述 ({len(jds)})[/bold]")
            for f in jds:
                j_tree.add(f"{f['name']}  [dim]{f['size']//1024}KB[/dim]")

        # 笔记
        notes = self.storage.list_notes()
        if notes:
            n_tree = tree.add(f"[bold]📝 笔记 ({len(notes)})[/bold]")
            for n in notes[:10]:
                n_tree.add(f"{n.get('title', '未命名')}")

        # 画像
        profile = self.storage.load_profile()
        if profile:
            tree.add(f"[bold]👤 候选人画像[/bold]")

        console.print(tree)

        if not any([resumes, projects, jds, notes, profile]):
            return "[dim]素材库为空。使用 material import <路径> 导入素材。[/dim]"
        return ""

    # ─── search ──────────────────────────────────────────

    def _cmd_search(self, args: str) -> str:
        keyword = args.strip()
        if not keyword:
            return "[red]请输入搜索关键词[/red]"

        files = self.storage.list_raw_files()
        results = []

        for f in files:
            try:
                content = Path(f["path"]).read_text(encoding="utf-8", errors="replace")
                if keyword.lower() in content.lower():
                    # 找关键词上下文
                    idx = content.lower().index(keyword.lower())
                    start = max(0, idx - 60)
                    end = min(len(content), idx + len(keyword) + 120)
                    context = content[start:end]
                    results.append({
                        "file": f["name"],
                        "category": f["category"],
                        "context": context.strip()[:200],
                    })
            except Exception:
                continue

        if not results:
            # 用 LLM 智能搜索
            console.print("[dim]未找到精确匹配，尝试语义搜索...[/dim]")
            return self._semantic_search(keyword, files)

        table = Table(title=f"'{keyword}' 搜索结果 ({len(results)} 条)", box=box.SIMPLE)
        table.add_column("文件", style="cyan")
        table.add_column("分类", style="green")
        table.add_column("上下文")
        for r in results[:10]:
            table.add_row(r["file"], r["category"], r["context"][:80] + "...")
        console.print(table)
        return ""

    def _semantic_search(self, keyword: str, files: list[dict]) -> str:
        """用 LLM 进行语义搜索。"""
        summaries = []
        for f in files[:8]:  # 最多搜 8 个文件
            try:
                content = Path(f["path"]).read_text(encoding="utf-8", errors="replace")[:2000]
                summaries.append(f"【{f['name']}】\n{content[:500]}")
            except Exception:
                continue

        if not summaries:
            return "[yellow]素材库为空，无法搜索[/yellow]"

        system = "你是一个素材搜索助手。根据用户的关键词，从以下素材中找出相关的内容，并返回匹配的文件名和摘要。"
        resp = chat(system=system, messages=[
            {"role": "user", "content": f"关键词：{keyword}\n\n素材：\n\n" + "\n---\n".join(summaries)}
        ], temperature=0.3)
        console.print(Panel(resp, title=f"🔍 语义搜索: {keyword}", border_style="yellow"))
        return ""

    # ─── profile ─────────────────────────────────────────

    def _cmd_profile(self, args: str = "") -> str:
        """基于所有素材生成/更新候选人画像。"""
        files = self.storage.list_raw_files()
        if not files:
            return "[yellow]素材库为空，请先导入素材[/yellow]"

        console.print("[dim]正在综合分析素材，生成候选人画像...[/dim]")

        # 收集所有素材内容
        materials_text = []
        for f in files:
            try:
                content = Path(f["path"]).read_text(encoding="utf-8", errors="replace")[:5000]
                materials_text.append(f"【{f['category']}/{f['name']}】\n{content[:2000]}")
            except Exception:
                continue

        all_text = "\n---\n".join(materials_text)

        # 读取索引中的结构化信息增强
        index = self.storage.get_index()

        system = """你是一个专业的 B 端产品经理简历分析师。请根据所有素材生成一个完整的候选人画像。

输出 JSON 格式：
{
    "name": "姓名",
    "target_positions": ["目标岗位1", "目标岗位2"],
    "current_title": "当前职位",
    "years_of_experience": 5,
    "education": [{"school": "...", "degree": "...", "major": "..."}],
    "core_skills": ["技能1", "技能2"],
    "career_summary": "职业简介（50字以内）",
    "key_projects": [{"name": "项目名", "role": "角色", "metrics": ["量化成果1"]}],
    "b2b_domain_expertise": ["领域专长"],
    "highlight_achievements": ["亮点成就"],
    "weak_areas": ["需加强的方面"]
}"""

        try:
            result = chat_json(system=system, messages=[
                {"role": "user", "content": f"素材内容：\n\n{all_text[:30000]}"}
            ], temperature=0.3)
        except Exception as e:
            return f"[red]画像生成失败: {e}[/red]"

        profile = UserProfile(**result)
        self.storage.save_profile(profile)

        # 显示画像
        console.print(Panel(f"""
[bold]👤 候选人画像[/bold]

[bold]姓名:[/bold] {profile.name}
[bold]目标岗位:[/bold] {', '.join(profile.target_positions)}
[bold]当前职位:[/bold] {profile.current_title}
[bold]经验年限:[/bold] {profile.years_of_experience} 年

[bold]核心技能:[/bold]
{chr(10).join(f'  • {s}' for s in profile.core_skills)}

[bold]B端领域专长:[/bold]
{chr(10).join(f'  • {d}' for d in profile.b2b_domain_expertise)}

[bold]亮点成就:[/bold]
{chr(10).join(f'  • {a}' for a in profile.highlight_achievements)}

[bold]需加强:[/bold]
{chr(10).join(f'  • {w}' for w in profile.weak_areas)}
        """.strip(), title="📋 候选人画像", border_style="cyan"))

        return ""
