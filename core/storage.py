"""本地文件存储 — 管理所有素材和数据的持久化

═══════════════════════════════════════════════════════════════════════════════
架构设计说明（AI 产品经理视角）
═══════════════════════════════════════════════════════════════════════════════

一、为什么用本地文件系统而不是数据库？

  1. 数据量小：个人面试准备，素材文件数量在几十到几百级别
  2. 零运维：不需要安装/配置 MySQL/PostgreSQL/SQLite
  3. 可查看：所有数据都是 JSON 文件，用户可以直接打开查看/手动修改
  4. 可备份：整个 data/ 目录就是一个备份单元，git 或云盘即可同步

  什么时候该换数据库：
    - 用户数超过 1（多租户）
    - 素材文件超过 10,000 个
    - 需要并发写入（多人协作场景）
    以上条件目前都不满足，所以文件系统是最优解。

二、目录结构设计

  data/
  ├── materials/
  │   ├── index.json          ← 素材库索引（文件名→类别→标题的映射表）
  │   ├── raw/                ← 原始文件（用户上传的简历/项目/JD/图片）
  │   │   ├── resumes/
  │   │   ├── projects/
  │   │   ├── jds/
  │   │   └── images/
  │   ├── profiles/           ← 用户画像（LLM 合成的候选人全景图）
  │   │   └── profile.json
  │   └── notes/              ← 用户笔记（面试准备中保存的内容）
  │       └── note_YYYYMMDD_HHMMSS.json
  ├── sessions/               ← 模拟面试记录
  │   └── mock_<公司>_<岗位>_<日期>.json
  └── interviews.json         ← 真实面试追踪记录

  设计考量：
    - raw/ 保留原始文件名，方便用户通过文件名识别
    - notes/ 以时间戳命名，保证不重名且按时间排序
    - sessions/ 以公司+岗位+日期命名，方便查找特定面试记录

三、索引与物理文件分离

  index.json 是一个轻量级的元数据映射表，存储每个素材的：
    - 文件名、路径、类型、标题、导入时间
    - LLM 提取的结构化摘要（如果提取成功）

  为什么要分离：
    1. list 操作只需读 index.json（几 KB），不需要遍历原始文件
    2. 原始文件可能是 PDF/XLSX/图片等不可直接搜索的格式，索引统一为文本
    3. 索引损坏不影响原始文件，重建索引即可恢复

四、为什么没有缓存层？

  当前数据量下，读 JSON 文件的 I/O 时间远小于 LLM API 调用时间，
  缓存带来的性能提升微不足道，但引入了一致性问题（缓存失效、脏读）。
  如果某天素材库超过 1000 个文件，可以在 get_index() 中加内存缓存。
═══════════════════════════════════════════════════════════════════════════════
"""
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
    """统一存储管理 — 负责所有文件读写、目录维护、索引管理。

    这是项目中唯一直接操作文件系统的类。所有 Skill 通过 StorageManager
    读写数据，不直接操作文件路径。这样做的好处：
      - 如果以后切换存储后端（如 SQLite），只需修改这一个类
      - 文件路径逻辑集中管理，不会散落在各个 Skill 中
      - 索引一致性由 StorageManager 保证，不会出现多写者冲突
    """

    def __init__(self, base_dir: str = "./data"):
        """初始化存储管理器。

        Args:
            base_dir: 数据根目录，默认 ./data，启动时自动创建子目录结构。
                      使用 resolve() 转为绝对路径，避免工作目录切换导致路径不一致。
        """
        self.base = Path(base_dir).resolve()
        self._ensure_dirs()

    # ─── 目录初始化 ──────────────────────────────────────────────────────────
    # 在 __init__ 中自动创建所有需要的子目录，确保后续写入操作不会因目录缺失失败。
    # mkdir(parents=True, exist_ok=True) 是幂等的，重复调用不会出错。

    def _ensure_dirs(self):
        """确保所有数据子目录存在。如果目录已存在，静默跳过。"""
        for sub in [
            "materials/profiles",       # 用户画像
            "materials/raw/resumes",    # 简历原始文件
            "materials/raw/projects",   # 项目文档原始文件
            "materials/raw/jds",        # 岗位描述原始文件
            "materials/raw/images",     # 图片素材
            "materials/notes",          # 用户笔记
            "sessions",                 # 模拟面试会话记录
        ]:
            (self.base / sub).mkdir(parents=True, exist_ok=True)

    # ═══════════════════════════════════════════════════════════════════════════
    # 基础文件操作：复制、JSON 读写、文本读写
    # 所有上层逻辑（索引管理、笔记保存、会话存档）都基于这些基础方法
    # ═══════════════════════════════════════════════════════════════════════════

    def copy_file(self, src: str, category: str) -> str | None:
        """将外部文件复制到素材库 raw 目录，返回目标路径。

        设计考量：
          - 复制而非移动：保留用户原始文件不动，素材库是独立副本
          - 同名文件自动加时间戳后缀：防止覆盖，保留所有历史版本
          - 返回目标路径：调用方可以用这个路径更新索引

        Args:
            src: 源文件路径（用户本地文件）
            category: 素材类别，映射到 raw 子目录
                      resume → raw/resumes
                      project → raw/projects
                      jd → raw/jds
                      image → raw/images
                      其他 → 回退到 raw/others

        Returns:
            目标文件路径，源文件不存在则返回 None
        """
        src_path = Path(src)
        if not src_path.exists():
            return None
        # 类别 → 子目录映射（白名单，防止路径穿越）
        category_map = {"resume": "resumes", "project": "projects", "jd": "jds", "image": "images"}
        target_dir = self.base / "materials" / "raw" / category_map.get(category, "others")
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / src_path.name
        # 同名文件不覆盖，自动追加时间戳
        if target.exists():
            stem = target.stem
            suffix = target.suffix
            target = target_dir / f"{stem}_{datetime.now().strftime('%H%M%S')}{suffix}"
        # copy2 保留文件修改时间等元数据
        shutil.copy2(str(src_path), str(target))
        return str(target)

    def save_json(self, path: str, data: dict):
        """保存 JSON 文件到 data/ 下的相对路径。

        ensure_ascii=False 保证中文正常显示（不转义为 unicode 转义序列），
        indent=2 保证 JSON 可读性（用户可以直接打开查看/编辑）。

        Args:
            path: 相对于 base_dir 的路径，如 "materials/index.json"
            data: 要保存的字典数据
        """
        full = self.base / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    def load_json(self, path: str) -> dict | list:
        """加载 JSON 文件。文件不存在时返回空 dict（index.json）或空 list。

        为什么文件不存在不抛异常：
          - 首次使用没有索引文件是正常情况，应该静默初始化
          - 调用方不需要到处写 try-except

        Args:
            path: 相对于 base_dir 的路径

        Returns:
            解析后的 dict/list，文件不存在时返回 {}
        """
        full = self.base / path
        if not full.exists():
            return {} if path.endswith("index.json") else []
        return json.loads(full.read_text())

    def save_text(self, path: str, content: str):
        """保存纯文本文件。用于笔记内容、LLM 响应的原始文本等。

        Args:
            path: 相对于 base_dir 的路径
            content: 文本内容
        """
        full = self.base / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content)

    def load_text(self, path: str) -> str:
        """加载纯文本文件。文件不存在返回空字符串。"""
        full = self.base / path
        return full.read_text() if full.exists() else ""

    def list_raw_files(self, category: str = "") -> list[dict]:
        """列出 raw 目录下的所有文件（元数据列表）。

        这是素材库浏览功能的数据来源。遍历 raw/ 下的所有子目录，
        收集每个文件的名称、路径、类别、大小。

        Args:
            category: 可选，只列出指定类别（resumes/projects/jds/images），
                      为空则列出全部

        Returns:
            文件元数据列表 [{name, path, category, size}]，
            按类别→文件名的字母序排列
        """
        raw = self.base / "materials" / "raw"
        if not raw.exists():
            return []
        results = []
        for sub in sorted(raw.iterdir()):       # 按类别字母序
            if sub.is_dir() and (not category or sub.name == category):
                for f in sorted(sub.iterdir()):  # 按文件名字母序
                    if f.is_file() and not f.name.startswith("."):  # 跳过隐藏文件
                        results.append({
                            "name": f.name,
                            "path": str(f),
                            "category": sub.name,
                            "size": f.stat().st_size,
                        })
        return results

    # ═══════════════════════════════════════════════════════════════════════════
    # 素材库索引管理
    # index.json 是所有素材的「目录表」，存储元数据而非文件本身
    # ═══════════════════════════════════════════════════════════════════════════

    def get_index(self) -> dict:
        """读取素材库索引，不存在时返回空索引结构。

        Returns:
            {
                "resumes": [{file, path, type, title, imported_at, ...}],
                "projects": [...],
                "jds": [...],
                "images": [...],
                "notes": [...],
                "updated_at": "ISO时间戳"
            }
        """
        return self.load_json("materials/index.json") or {
            "resumes": [],
            "projects": [],
            "jds": [],
            "images": [],
            "notes": [],
            "updated_at": "",
        }

    def save_index(self, index: dict):
        """保存素材库索引，自动更新 updated_at 时间戳。

        所有对索引的修改（增删改素材条目）最终都通过这个方法写入。
        updated_at 用于判断索引是否过期，目前仅在 Obsidian 连接器的缓存
        分析中使用。
        """
        index["updated_at"] = datetime.now().isoformat()
        self.save_json("materials/index.json", index)

    # ─── 画像管理 ──────────────────────────────────────────────────────────
    # 用户画像是从所有素材中 LLM 合成的候选人全景图。
    # 存储在 materials/profiles/profile.json，单一文件覆盖写入。
    # 这是整个系统的核心资产，所有面试准备和模拟面试都基于此。

    def save_profile(self, profile: UserProfile):
        """保存用户画像。支持 UserProfile 对象和 dict 两种输入。

        Args:
            profile: UserProfile 实例或 dict
        """
        self.save_json("materials/profiles/profile.json", profile.to_dict() if hasattr(profile, 'to_dict') else profile)

    def save_profile_data(self, data: dict):
        """直接保存画像 dict 到文件。

        与 save_profile 的区别：跳过 to_dict() 调用，直接存 dict。
        用于 demo 种子数据写入和手动构造画像的场景。

        Args:
            data: 画像字段的字典
        """
        self.save_json("materials/profiles/profile.json", data)

    def load_profile(self) -> UserProfile | None:
        """加载用户画像，不存在时返回 None。"""
        data = self.load_json("materials/profiles/profile.json")
        if not data:
            return None
        # 检查是否为 dataclass 类型（避免对 UserProfile 实例重复转换）
        if isinstance(data, dict) and "__dataclass_fields__" not in str(type(data)):
            return UserProfile(**data)
        return data

    # ─── 笔记管理 ──────────────────────────────────────────────────────────
    # 笔记以时间戳命名的独立 JSON 文件存储在 materials/notes/ 下。
    # 每条笔记一个文件，方便单独查看、编辑、删除。

    def save_note(self, note: NoteInfo):
        """保存一条笔记为独立 JSON 文件。

        Args:
            note: NoteInfo 实例，包含标题、内容、来源、标签、创建时间
        """
        filename = f"note_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        self.save_json(f"materials/notes/{filename}", note.to_dict() if hasattr(note, 'to_dict') else note.__dict__)

    def list_notes(self) -> list[dict]:
        """列出所有笔记，按时间倒序。

        Returns:
            笔记列表 [{title, content, source, tags, created_at, _file}]
            _file 字段是附加的文件名，方便后续定位和删除
        """
        notes_dir = self.base / "materials" / "notes"
        if not notes_dir.exists():
            return []
        notes = []
        for f in sorted(notes_dir.iterdir(), reverse=True):  # 倒序：最新的在前
            if f.suffix == ".json":
                data = json.loads(f.read_text())
                data["_file"] = f.name  # 附加文件名，方便后续操作
                notes.append(data)
        return notes

    # ─── 模拟面试会话管理 ──────────────────────────────────────────────────
    # 每次模拟面试保存为一个 JSON 文件，以公司+岗位+日期命名。

    def save_session(self, session: MockSession):
        """保存一次模拟面试的完整记录。

        文件名格式：mock_<公司>_<岗位>_<日期>.json
        如果同一天同一岗位多次模拟，会覆盖上一次记录。
        如需保留历史，可在文件名中加入时间。

        Args:
            session: MockSession 实例，包含所有问答和评分
        """
        filename = f"mock_{session.company}_{session.position}_{session.started_at[:10]}.json"
        self.save_json(f"sessions/{filename}", session.to_dict())

    def list_sessions(self) -> list[dict]:
        """列出所有模拟面试记录，按文件时间倒序。

        Returns:
            会话列表，最新的在最前面
        """
        sess_dir = self.base / "sessions"
        if not sess_dir.exists():
            return []
        sessions = []
        for f in sorted(sess_dir.iterdir(), reverse=True):
            if f.suffix == ".json":
                sessions.append(json.loads(f.read_text()))
        return sessions

    # ─── 面试追踪管理 ──────────────────────────────────────────────────────
    # 真实面试记录存储在一个统一的 interviews.json 文件中（数组）。
    # 与模拟面试不同：真实面试记录量不大（一个月几次），统一文件管理更方便。

    def save_interviews(self, records: list[dict]):
        """保存全部面试追踪记录（覆盖写入）。"""
        self.save_json("interviews.json", records)

    def load_interviews(self) -> list[dict]:
        """加载面试追踪记录列表。"""
        return self.load_json("interviews.json") or []

    # ─── v2.0 简历库管理 ────────────────────────────────────────────────────

    def save_resume(self, file_name: str, file_bytes: bytes) -> str:
        """保存一份 PDF 简历到 data/resumes/ 目录。

        Returns:
            保存后的文件绝对路径
        """
        resume_dir = self.base / "resumes"
        resume_dir.mkdir(parents=True, exist_ok=True)
        dest = resume_dir / file_name
        dest.write_bytes(file_bytes)
        return str(dest)

    def list_resumes(self) -> list[dict]:
        """列出简历库中所有 PDF 简历。

        Returns:
            简历元数据列表，每项含 file_name, file_path, uploaded_at
        """
        resume_dir = self.base / "resumes"
        if not resume_dir.exists():
            return []
        resumes = []
        for f in sorted(resume_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
            if f.suffix.lower() == ".pdf":
                resumes.append({
                    "file_name": f.name,
                    "file_path": str(f),
                    "display_name": f.stem,
                    "uploaded_at": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                })
        return resumes

    def delete_resume(self, file_name: str) -> bool:
        """删除一份简历文件。

        Returns:
            是否成功删除
        """
        file_path = self.base / "resumes" / file_name
        if file_path.exists():
            file_path.unlink()
            return True
        return False

    def resume_exists(self, file_name: str) -> bool:
        """检查简历文件是否已存在。"""
        return (self.base / "resumes" / file_name).exists()

    # ─── v2.0 岗位库管理 ────────────────────────────────────────────────────

    def _positions_file(self) -> Path:
        """岗位库 index.json 路径。"""
        pos_dir = self.base / "positions"
        pos_dir.mkdir(parents=True, exist_ok=True)
        return pos_dir / "index.json"

    def list_positions(self) -> list[dict]:
        """列出所有岗位信息。

        Returns:
            岗位列表（按创建时间倒序）
        """
        positions = self.load_json(str(self._positions_file()))
        if isinstance(positions, list):
            return sorted(positions, key=lambda x: x.get("created_at", ""), reverse=True)
        return []

    def save_position(self, data: dict) -> None:
        """保存一条岗位信息到 index.json。

        Args:
            data: 岗位字典，需含 company, position, responsibilities, requirements
        """
        data.setdefault("created_at", datetime.now().isoformat())
        positions = self.list_positions()
        positions.insert(0, data)
        self.save_json(str(self._positions_file()), positions)

    def update_position(self, index: int, data: dict) -> None:
        """更新指定索引的岗位信息。"""
        positions = self.list_positions()
        if 0 <= index < len(positions):
            positions[index] = data
            self.save_json(str(self._positions_file()), positions)

    def delete_position(self, index: int) -> None:
        """删除指定索引的岗位信息。"""
        positions = self.list_positions()
        if 0 <= index < len(positions):
            positions.pop(index)
            self.save_json(str(self._positions_file()), positions)
