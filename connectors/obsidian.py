"""Obsidian Vault 连接器 — 搜索、读取、导入素材

设计原则：
- 按需索引：首次调用时扫描文件结构，不预加载内容
- 搜索即服务：搜索时实时提取匹配文件的文本
- 导入需确认：搜索到文件后，用户确认后才导入素材库
"""
from __future__ import annotations
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.tree import Tree
from rich import box

from core.storage import StorageManager

console = Console()

# 可提取文本的文件类型
_TEXT_EXTENSIONS = {".md", ".txt", ".csv", ".json", ".yaml", ".yml", ".xml", ".html"}
# 可提取文本的办公文档
_OFFICE_EXTENSIONS = {".pdf", ".docx", ".pptx"}

# PDF 提取缓存目录
_CACHE_DIR = Path(__file__).parent.parent / "data" / "obsidian_cache"


class ObsidianConnector:
    """Obsidian Vault 连接器"""

    def __init__(self, vault_path: str, storage: StorageManager):
        self.vault_path = Path(vault_path).resolve()
        self.storage = storage
        self._index: list[dict] = []  # [{path, name, ext, dir, size, mtime}]
        self._indexed_at: str = ""

    # ─── 索引 ────────────────────────────────────────────

    def _scan(self, force: bool = False) -> list[dict]:
        """扫描 Vault 文件结构，缓存到内存和磁盘。"""
        if self._index and not force:
            return self._index

        cache_file = _CACHE_DIR / "vault_index.json"
        if not force and cache_file.exists():
            cached = json.loads(cache_file.read_text())
            if cached.get("vault_path") == str(self.vault_path):
                self._index = cached["files"]
                self._indexed_at = cached.get("indexed_at", "")
                return self._index

        console.print("[dim]正在扫描 Obsidian Vault...[/dim]")
        files = []
        # 忽略隐藏目录和特定文件夹
        skip_dirs = {".obsidian", ".git", "__pycache__", "node_modules"}

        for f in self.vault_path.rglob("*"):
            if f.is_dir():
                continue
            # 跳过隐藏目录和系统文件
            rel = f.relative_to(self.vault_path)
            if any(part.startswith(".") or part in skip_dirs for part in rel.parts):
                continue
            if f.name.startswith("."):
                continue
            if f.suffix.lower() in _TEXT_EXTENSIONS | _OFFICE_EXTENSIONS | {".xlsx", ".xls"}:
                files.append({
                    "path": str(f),
                    "name": f.name,
                    "ext": f.suffix.lower(),
                    "dir": str(rel.parent) if str(rel.parent) != "." else "",
                    "size": f.stat().st_size,
                    "mtime": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                })

        self._index = sorted(files, key=lambda x: x["dir"] + x["name"])
        self._indexed_at = datetime.now().isoformat()

        # 缓存到磁盘
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps({
            "vault_path": str(self.vault_path),
            "indexed_at": self._indexed_at,
            "files": self._index,
        }, ensure_ascii=False, indent=2))

        console.print(f"[dim]✓ 扫描完成: {len(self._index)} 个文件[/dim]")
        return self._index

    def refresh_index(self):
        """强制重建索引。"""
        self._scan(force=True)

    # ─── 搜索 ────────────────────────────────────────────

    def search(self, keyword: str, max_results: int = 20) -> list[dict]:
        """全文搜索 Vault 中的文件。返回匹配的文件列表。"""
        files = self._scan()
        keyword_lower = keyword.lower()

        # 第一阶段：文件名匹配（快速）
        name_matches = [
            f for f in files
            if keyword_lower in f["name"].lower()
        ]

        # 第二阶段：内容匹配（对文本文件提取内容搜索）
        content_matches = self._search_content(keyword, [f for f in files if f not in name_matches])

        # 合并结果，去重
        seen = set()
        results = []
        for f in name_matches + content_matches:
            if f["path"] not in seen:
                seen.add(f["path"])
                results.append(f)
                if len(results) >= max_results:
                    break

        return results

    def _search_content(self, keyword: str, files: list[dict]) -> list[dict]:
        """在文件内容中搜索关键词。"""
        matches = []
        keyword_lower = keyword.lower()

        # 只搜索 .md 和 .txt 文件（PDF 太慢，按需提取）
        text_files = [f for f in files if f["ext"] in {".md", ".txt", ".csv"}]

        with ThreadPoolExecutor(max_workers=8) as pool:
            future_map = {}
            for f in text_files:
                future = pool.submit(self._file_contains_text, f["path"], keyword_lower)
                future_map[future] = f

            for future in as_completed(future_map):
                f = future_map[future]
                try:
                    if future.result():
                        matches.append(f)
                except Exception:
                    pass

        return matches

    def _file_contains_text(self, path: str, keyword_lower: str) -> bool:
        """检查文件是否包含关键词。"""
        try:
            content = Path(path).read_text(encoding="utf-8", errors="replace")
            return keyword_lower in content.lower()
        except Exception:
            return False

    # ─── 读取文件 ────────────────────────────────────────

    def read_file(self, path: str, max_chars: int = 10000) -> str | None:
        """读取文件内容（支持 .md/.txt 直接读，PDF 提取）。"""
        p = Path(path)
        if not p.exists():
            return None

        ext = p.suffix.lower()

        if ext in _TEXT_EXTENSIONS:
            return p.read_text(encoding="utf-8", errors="replace")[:max_chars]

        elif ext == ".pdf":
            return self._extract_pdf_text(str(p))[:max_chars]

        else:
            return f"[不支持预览的文件类型: {ext}]"

    def _extract_pdf_text(self, path: str) -> str:
        """提取 PDF 文本（使用 pdfminer，带缓存）。"""
        cache_key = path.replace("/", "_").replace(" ", "_")
        cache_file = _CACHE_DIR / f"pdf_{cache_key}.txt"

        if cache_file.exists():
            return cache_file.read_text(encoding="utf-8", errors="replace")

        try:
            from pdfminer.high_level import extract_text
            text = extract_text(path)
            text = text.strip()
            # 缓存
            if text:
                cache_file.write_text(text, encoding="utf-8")
            return text
        except Exception as e:
            return f"[PDF 提取失败: {e}]"

    # ─── 展示 ────────────────────────────────────────────

    def display_tree(self, max_depth: int = 2):
        """展示 Vault 目录树。"""
        files = self._scan()

        tree = Tree(f"[bold]📒 Obsidian Vault: {self.vault_path.name}[/bold]")
        tree.add(f"[dim]{len(files)} 个文件 · 更新于 {self._indexed_at[:10]}[/dim]")

        # 按目录聚合
        dirs = {}
        for f in files:
            d = f["dir"]
            if d not in dirs:
                dirs[d] = {"files": 0, "pdfs": 0, "mds": 0}
            dirs[d]["files"] += 1
            if f["ext"] == ".pdf":
                dirs[d]["pdfs"] += 1
            elif f["ext"] == ".md":
                dirs[d]["mds"] += 1

        for d in sorted(dirs.keys()):
            if d.count("/") >= max_depth:
                continue
            info = dirs[d]
            label = d if d else "(根目录)"
            parts = []
            if info["mds"]:
                parts.append(f"{info['mds']} 📝")
            if info["pdfs"]:
                parts.append(f"{info['pdfs']} 📄")
            if info["files"] - info["mds"] - info["pdfs"]:
                parts.append(f"{info['files'] - info['mds'] - info['pdfs']} 📎")
            tree.add(f"[bold]{label}[/bold]  [dim]{' · '.join(parts)}[/dim]")

        console.print(tree)

    def display_results(self, results: list[dict], keyword: str = ""):
        """展示搜索结果表格。"""
        if not results:
            console.print(f"[yellow]未找到与 '{keyword}' 相关的文件[/yellow]")
            return

        title = f"在 Vault 中找到 {len(results)} 个文件"
        if keyword:
            title += f" (关键词: {keyword})"

        table = Table(title=title, box=box.SIMPLE)
        table.add_column("#", style="dim", width=3)
        table.add_column("文件名", style="cyan")
        table.add_column("目录")
        table.add_column("类型", width=5)
        table.add_column("大小")

        for i, f in enumerate(results[:30], 1):
            ext_icon = {"pdf": "📄", ".md": "📝", ".txt": "📄", ".csv": "📊", ".xlsx": "📊", ".docx": "📄"}.get(f["ext"], "📎")
            size_str = f"{f['size'] // 1024}KB" if f['size'] > 1024 else f"{f['size']}B"
            table.add_row(
                str(i),
                f["name"],
                f["dir"][:40],
                ext_icon,
                size_str,
            )
        console.print(table)

    # ─── 导入素材库 ──────────────────────────────────────

    def import_to_material(self, file_path: str) -> str:
        """将 Vault 中的文件导入 Agent 素材库并提取结构化信息。"""
        p = Path(file_path)
        if not p.exists():
            return f"[red]文件不存在: {file_path}[/red]"

        # 提取文本内容
        content = self.read_file(file_path, max_chars=15000)
        if not content or content.startswith("[不支持"):
            return f"[red]无法提取文本: {file_path}[/red]"

        # 确定素材类型
        name = p.name.lower()
        if any(k in name for k in ["简历", "resume", "cv"]):
            category = "resume"
        elif any(k in name for k in ["jd", "岗位", "职位"]):
            category = "jd"
        else:
            category = "project"

        # 复制文件到素材库
        target = self.storage.copy_file(str(p), category)
        if not target:
            return f"[red]文件复制失败[/red]"

        # 保存提取的文本（以便后续 LLM 处理）
        text_path = Path(target).with_suffix(".txt")
        Path(text_path).write_text(content, encoding="utf-8")

        # 更新索引
        index = self.storage.get_index()
        key_map = {"resume": "resumes", "project": "projects", "jd": "jds"}
        entry = {
            "file": Path(target).name,
            "path": target,
            "type": category,
            "title": name,
            "source": "obsidian",
            "imported_at": datetime.now().isoformat(),
        }
        index.get(key_map.get(category, "projects"), []).append(entry)
        self.storage.save_index(index)

        return (
            f"[green]✓ 已导入到素材库: {p.name}[/green]\n"
            f"[dim]类别: {category}[/dim]\n"
            f"[dim]执行 material profile 可重新生成画像[/dim]"
        )

    def batch_import(self, file_paths: list[str]) -> list[str]:
        """批量导入文件到素材库。"""
        results = []
        for fp in file_paths:
            try:
                result = self.import_to_material(fp)
                results.append(result)
                console.print(result)
            except Exception as e:
                results.append(f"[red]导入失败 {fp}: {e}[/red]")
        return results
