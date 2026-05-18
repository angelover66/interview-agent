"""本地文件存储 — 管理所有素材和数据的持久化"""
from __future__ import annotations
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

from .models import (
    ResumeInfo, ProjectInfo, JDInfo, NoteInfo, UserProfile,
    MockSession, InterviewRecord,
)


class StorageManager:
    """统一存储管理，负责所有文件读写。"""

    def __init__(self, base_dir: str = "./data"):
        self.base = Path(base_dir).resolve()
        self._ensure_dirs()

    # ─── 目录结构 ────────────────────────────────────────

    def _ensure_dirs(self):
        for sub in [
            "materials/profiles",
            "materials/raw/resumes",
            "materials/raw/projects",
            "materials/raw/jds",
            "materials/raw/images",
            "materials/notes",
            "sessions",
        ]:
            (self.base / sub).mkdir(parents=True, exist_ok=True)

    # ─── 文件操作 ────────────────────────────────────────

    def copy_file(self, src: str, category: str) -> str | None:
        """将文件复制到素材 raw 目录，返回目标路径。"""
        src_path = Path(src)
        if not src_path.exists():
            return None
        category_map = {"resume": "resumes", "project": "projects", "jd": "jds", "image": "images"}
        target_dir = self.base / "materials" / "raw" / category_map.get(category, "others")
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / src_path.name
        # 同名文件自动加后缀
        if target.exists():
            stem = target.stem
            suffix = target.suffix
            target = target_dir / f"{stem}_{datetime.now().strftime('%H%M%S')}{suffix}"
        shutil.copy2(str(src_path), str(target))
        return str(target)

    def save_json(self, path: str, data: dict):
        """保存 JSON 文件。"""
        full = self.base / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    def load_json(self, path: str) -> dict | list:
        """加载 JSON 文件。"""
        full = self.base / path
        if not full.exists():
            return {} if path.endswith("index.json") else []
        return json.loads(full.read_text())

    def save_text(self, path: str, content: str):
        """保存文本文件。"""
        full = self.base / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content)

    def load_text(self, path: str) -> str:
        full = self.base / path
        return full.read_text() if full.exists() else ""

    def list_raw_files(self, category: str = "") -> list[dict]:
        """列出 raw 目录下的文件。"""
        raw = self.base / "materials" / "raw"
        if not raw.exists():
            return []
        results = []
        for sub in sorted(raw.iterdir()):
            if sub.is_dir() and (not category or sub.name == category):
                for f in sorted(sub.iterdir()):
                    if f.is_file() and not f.name.startswith("."):
                        results.append({
                            "name": f.name,
                            "path": str(f),
                            "category": sub.name,
                            "size": f.stat().st_size,
                        })
        return results

    # ─── 素材库索引 ──────────────────────────────────────

    def get_index(self) -> dict:
        return self.load_json("materials/index.json") or {
            "resumes": [],
            "projects": [],
            "jds": [],
            "images": [],
            "notes": [],
            "updated_at": "",
        }

    def save_index(self, index: dict):
        index["updated_at"] = datetime.now().isoformat()
        self.save_json("materials/index.json", index)

    # ─── 画像管理 ────────────────────────────────────────

    def save_profile(self, profile: UserProfile):
        self.save_json("materials/profiles/profile.json", profile.to_dict() if hasattr(profile, 'to_dict') else profile)

    def save_profile_data(self, data: dict):
        """直接保存画像 dict 到文件（用于 demo 种子数据）。"""
        self.save_json("materials/profiles/profile.json", data)

    def load_profile(self) -> UserProfile | None:
        data = self.load_json("materials/profiles/profile.json")
        if not data:
            return None
        if isinstance(data, dict) and "__dataclass_fields__" not in str(type(data)):
            return UserProfile(**data)
        return data

    # ─── 笔记管理 ────────────────────────────────────────

    def save_note(self, note: NoteInfo):
        filename = f"note_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        self.save_json(f"materials/notes/{filename}", note.to_dict() if hasattr(note, 'to_dict') else note.__dict__)

    def list_notes(self) -> list[dict]:
        notes_dir = self.base / "materials" / "notes"
        if not notes_dir.exists():
            return []
        notes = []
        for f in sorted(notes_dir.iterdir(), reverse=True):
            if f.suffix == ".json":
                data = json.loads(f.read_text())
                data["_file"] = f.name
                notes.append(data)
        return notes

    # ─── 模拟面试会话 ────────────────────────────────────

    def save_session(self, session: MockSession):
        filename = f"mock_{session.company}_{session.position}_{session.started_at[:10]}.json"
        self.save_json(f"sessions/{filename}", session.to_dict())

    def list_sessions(self) -> list[dict]:
        sess_dir = self.base / "sessions"
        if not sess_dir.exists():
            return []
        sessions = []
        for f in sorted(sess_dir.iterdir(), reverse=True):
            if f.suffix == ".json":
                sessions.append(json.loads(f.read_text()))
        return sessions

    # ─── 面试追踪 ────────────────────────────────────────

    def save_interviews(self, records: list[dict]):
        self.save_json("interviews.json", records)

    def load_interviews(self) -> list[dict]:
        return self.load_json("interviews.json") or []
