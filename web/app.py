"""Streamlit Web UI for Interview Agent — Japanese Editorial redesign."""
from __future__ import annotations
import sys
import re
import os
import tempfile
from pathlib import Path
from io import StringIO
from datetime import datetime

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
import streamlit as st

# Load secrets into environment (for Streamlit Cloud deployment)
try:
    for key, value in st.secrets.items():
        if key not in os.environ:
            os.environ[key] = value
except Exception:
    pass

from rich.console import Console

from core.storage import StorageManager
from core.llm import chat, chat_json
from core.models import MockSession, MockQuestion, MockAnswer
from skills.material import MaterialSkill
from skills.prep import PrepSkill
from skills.mock import MockSkill

try:
    from connectors.obsidian import ObsidianConnector
except ImportError:
    ObsidianConnector = None

import skills.material as material_module
import skills.prep as prep_module
import skills.mock as mock_module

from web.ui import rich_to_html, rich_to_text
from web.styles import THEME_CSS

# ─── Page config ─────────────────────────────────────────

st.set_page_config(
    page_title="B端产品经理面试助手",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── CSS injection ──────────────────────────────────────

st.markdown(f"<style>{THEME_CSS}</style>", unsafe_allow_html=True)

# ─── Session state init ──────────────────────────────────

def init_session():
    """Initialize or restore session state."""
    if "storage" not in st.session_state:
        st.session_state.storage = StorageManager(base_dir="./data")

        config_path = Path(__file__).parent.parent / "config.yaml"
        config = yaml.safe_load(config_path.read_text()) if config_path.exists() else {}
        vault_path = config.get("obsidian", {}).get("vault_path", "")

        obsidian_connector = None
        if vault_path and Path(vault_path).exists() and ObsidianConnector is not None:
            obsidian_connector = ObsidianConnector(vault_path, st.session_state.storage)

        st.session_state.obsidian_connector = obsidian_connector
        st.session_state.vault_path = vault_path

        st.session_state.material = MaterialSkill(st.session_state.storage, obsidian_connector)
        st.session_state.prep = PrepSkill(st.session_state.storage, obsidian_connector)
        st.session_state.mock = MockSkill(st.session_state.storage)

        # Mock interview state
        st.session_state.mock_active = False
        st.session_state.mock_chat_history = []
        st.session_state.mock_started = False
        st.session_state.show_review = False

        # Prep conversation state
        st.session_state.prep_chat_history = []
        st.session_state.prep_target = ""

        # Current page (default to home)
        st.session_state.page = "首页"


# ─── Helpers ──────────────────────────────────────────────

def capture_output(skill_module, skill_instance, action: str, args: str = "") -> str:
    """Run a skill action and capture console output as plain text."""
    capture = StringIO()
    old_console = skill_module.console
    skill_module.console = Console(file=capture, force_terminal=False, width=100, color_system=None)
    try:
        result = skill_instance.run(action, args)
        captured = capture.getvalue()
    finally:
        skill_module.console = old_console
    if result and result.strip():
        return result
    return captured


def clean_rich(text: str) -> str:
    """Strip box-drawing characters and convert rich markup to HTML."""
    if not text or not text.strip():
        return ""
    cleaned = re.sub(r'[╭╮╰╯│├└┬┴┼═─━]', '', text).strip()
    return rich_to_html(cleaned)


def display_rich(text: str):
    """Display text with rich markup, converted to HTML."""
    if not text or not text.strip():
        return
    cleaned = clean_rich(text)
    if cleaned:
        st.markdown(cleaned, unsafe_allow_html=True)


def stylized_title(title: str):
    """Render a page title with the editorial style."""
    st.markdown(
        f'<h1 style="font-family:var(--font-display);color:var(--ink);margin-bottom:0.3rem;">{title}</h1>',
        unsafe_allow_html=True,
    )


def section_header(title: str):
    """Render a section header with the editorial style."""
    st.markdown(
        f'<h3 style="font-family:var(--font-display);color:var(--ink);margin-top:1rem;">{title}</h3>',
        unsafe_allow_html=True,
    )


def empty_state(icon: str, title: str, desc: str):
    """Render empty state placeholder."""
    st.markdown(f"""
    <div class="empty-state">
        <div class="empty-icon">{icon}</div>
        <div class="empty-title">{title}</div>
        <div class="empty-desc">{desc}</div>
    </div>
    """, unsafe_allow_html=True)


# ─── Navigation ──────────────────────────────────────────

NAV_ITEMS = [
    ("🏠", "首页"),
    ("📂", "素材库"),
    ("📖", "面试准备"),
    ("🎯", "模拟面试"),
]


def render_nav():
    """Render top navigation as a row of styled buttons."""
    col_spec = [1] * len(NAV_ITEMS) + [6]
    cols = st.columns(col_spec)

    for i, (icon, page) in enumerate(NAV_ITEMS):
        is_active = st.session_state.page == page
        with cols[i]:
            if st.button(
                f"{icon}  {page}",
                use_container_width=True,
                type="primary" if is_active else "secondary",
                key=f"nav_{page}",
            ):
                if st.session_state.page != page:
                    st.session_state.page = page
                    st.rerun()

    # Underline below nav
    st.markdown('<div class="nav-underline"></div>', unsafe_allow_html=True)


# ─── Page: Home ───────────────────────────────────────────

def page_home():
    storage = st.session_state.storage
    profile = storage.load_profile()

    # ── Hero / Profile ──
    if profile:
        st.markdown(f"""
        <div class="profile-hero">
            <div class="profile-name">{profile.name or '候选人'}</div>
            <div class="profile-role">{profile.current_title or ''} {('→ ' + ', '.join(profile.target_positions)) if profile.target_positions else ''}</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="profile-hero">
            <div class="profile-name">面试助手</div>
            <div class="profile-role">B端产品经理一站式面试准备平台</div>
        </div>
        """, unsafe_allow_html=True)

    # ── Stats row ──
    files = storage.list_raw_files()
    index = storage.get_index()
    material_count = len(files)
    resume_count = len(index.get("resumes", []))
    jd_count = len(index.get("jds", []))
    sessions = storage.list_sessions()
    session_count = len(sessions)

    avg_score = 0
    scored = [s.get("overall_score", 0) for s in sessions if s.get("overall_score")]
    if scored:
        avg_score = sum(scored) / len(scored)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("素材文件", material_count)
    with c2:
        st.metric("简历", resume_count)
    with c3:
        st.metric("目标岗位", jd_count)
    with c4:
        st.metric("模拟面试", session_count)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Quick actions ──
    section_header("快速开始")

    qc1, qc2, qc3 = st.columns(3)
    with qc1:
        st.markdown("""
        <div class="setup-section">
            <div style="font-size:2rem;margin-bottom:0.5rem;">📂</div>
            <h4>素材库</h4>
            <p style="font-size:0.85rem;color:var(--ink-light);">上传简历、JD、项目文档，构建个人面试素材库</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("导入素材", use_container_width=True, key="home_goto_material"):
            st.session_state.page = "素材库"
            st.rerun()

    with qc2:
        st.markdown("""
        <div class="setup-section">
            <div style="font-size:2rem;margin-bottom:0.5rem;">📖</div>
            <h4>面试准备</h4>
            <p style="font-size:0.85rem;color:var(--ink-light);">设定目标岗位，生成定制化学习材料与面试题预测</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("开始准备", use_container_width=True, key="home_goto_prep"):
            st.session_state.page = "面试准备"
            st.rerun()

    with qc3:
        st.markdown("""
        <div class="setup-section">
            <div style="font-size:2rem;margin-bottom:0.5rem;">🎯</div>
            <h4>模拟面试</h4>
            <p style="font-size:0.85rem;color:var(--ink-light);">AI 面试官角色扮演，多维度评估与反馈</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("开始面试", use_container_width=True, key="home_goto_mock"):
            st.session_state.page = "模拟面试"
            st.rerun()

    # ── Recent sessions ──
    if sessions:
        st.markdown("<br>", unsafe_allow_html=True)
        section_header("最近面试记录")
        for s in sessions[:5]:
            score = s.get("overall_score", 0)
            score_str = f"{score}/10" if score else "未评分"
            score_color = (
                "var(--sage)" if score >= 7
                else "var(--amber)" if score >= 5
                else "var(--vermillion)"
            )
            date_str = (s.get("started_at", "") or "")[:10]
            st.markdown(f"""
            <div class="history-item">
                <strong>{s.get('company', '?')}</strong> — {s.get('position', '?')}
                <span class="hi-date">{date_str}</span>
                <span class="hi-score" style="float:right;color:{score_color};">{score_str}</span>
            </div>
            """, unsafe_allow_html=True)

    # ── Profile summary (if exists) ──
    if profile:
        st.markdown("<br>", unsafe_allow_html=True)
        section_header("候选人画像概览")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"""
            <div class="editorial-card accent-left">
                <h4>核心技能</h4>
                <p style="font-size:0.9rem;">{' · '.join(profile.core_skills) if profile.core_skills else '暂无'}</p>
                <h4 style="margin-top:1rem;">B端专长</h4>
                <p style="font-size:0.9rem;">{' · '.join(profile.b2b_domain_expertise) if profile.b2b_domain_expertise else '暂无'}</p>
            </div>
            """, unsafe_allow_html=True)
        with c2:
            weaknesses = ' · '.join(profile.weak_areas) if profile.weak_areas else '暂无'
            st.markdown(f"""
            <div class="editorial-card">
                <h4>需加强</h4>
                <p style="font-size:0.9rem;color:var(--vermillion);">{weaknesses}</p>
                <h4 style="margin-top:1rem;">经验年限</h4>
                <p style="font-size:0.9rem;">{profile.years_of_experience} 年</p>
            </div>
            """, unsafe_allow_html=True)


# ─── Page: Material ───────────────────────────────────────

def page_material():
    stylized_title("素材库")

    tab1, tab2, tab3, tab4 = st.tabs(["导入", "浏览", "画像", "Obsidian"])

    # ── Tab 1: Import ──
    with tab1:
        st.markdown("""
        <div class="setup-section">
            <p style="font-size:0.9rem;color:var(--ink-light);margin-bottom:0.5rem;">
                支持 .txt / .md / .pdf / .xlsx / .xls / .png / .jpg / .webp 格式。
                上传后自动提取结构化信息并入库。
            </p>
        </div>
        """, unsafe_allow_html=True)

        uploaded = st.file_uploader(
            "拖拽或点击上传素材",
            type=["txt", "md", "pdf", "xlsx", "xls", "png", "jpg", "jpeg", "webp"],
            key="material_uploader",
            label_visibility="collapsed",
        )
        if uploaded:
            upload_dir = Path(tempfile.gettempdir()) / "interview_agent_uploads"
            upload_dir.mkdir(exist_ok=True)
            tmp_path = upload_dir / uploaded.name
            tmp_path.write_bytes(uploaded.read())

            with st.spinner("正在提取信息..."):
                try:
                    output = capture_output(material_module, st.session_state.material, "import", str(tmp_path))
                except Exception:
                    output = None

            tmp_path.unlink(missing_ok=True)
            if output:
                display_rich(output)
            st.success(f"「{uploaded.name}」已入库")

    # ── Tab 2: Browse ──
    with tab2:
        files = st.session_state.storage.list_raw_files()
        if not files:
            empty_state("📭", "素材库为空", "上传简历、JD 或项目文档开始构建素材库")
        else:
            keyword = st.text_input("搜索素材", placeholder="输入关键词筛选...", key="material_search", label_visibility="collapsed")

            display_files = files
            if keyword:
                display_files = []
                for f in files:
                    try:
                        content = Path(f["path"]).read_text(encoding="utf-8", errors="replace")
                        if keyword.lower() in content.lower():
                            display_files.append(f)
                    except Exception:
                        continue
                if not display_files:
                    st.caption("无匹配结果")

            # Card grid: 3 columns
            cols_per_row = 3
            for i in range(0, len(display_files), cols_per_row):
                row_files = display_files[i:i+cols_per_row]
                cols = st.columns(cols_per_row)
                for j, f in enumerate(row_files):
                    cat = f.get("category", "")
                    cat_emoji = {"resumes": "📄", "projects": "📁", "jds": "🎯", "images": "🖼️"}.get(cat, "📎")
                    is_image = cat == "images" or f.get("name", "").lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif"))
                    size_kb = f.get("size", 0) // 1024

                    with cols[j]:
                        # Card HTML
                        st.markdown(f"""
                        <div class="material-grid-card">
                            <div class="material-icon">{cat_emoji}</div>
                            <div class="material-name">{f['name']}</div>
                            <div class="material-meta">{size_kb}KB · {cat}</div>
                        </div>
                        """, unsafe_allow_html=True)

                        # Actions
                        bc1, bc2 = st.columns(2)
                        view_key = f"view_{f['path']}"
                        with bc1:
                            view_label = "🖼️ 预览" if is_image else "📖 查看"
                            if st.button(view_label, key=view_key, use_container_width=True):
                                st.session_state[f"viewing_{view_key}"] = not st.session_state.get(f"viewing_{view_key}", False)
                        with bc2:
                            if st.button("🗑 删除", key=f"del_{f['name']}", use_container_width=True):
                                st.session_state.material.run("delete", f["name"])
                                st.rerun()

                        # Preview expand
                        if st.session_state.get(f"viewing_{view_key}", False):
                            if is_image:
                                with st.expander("图片预览", expanded=True):
                                    try:
                                        st.image(f["path"], caption=f["name"], use_container_width=True)
                                    except Exception:
                                        st.error("无法加载图片")
                            else:
                                try:
                                    content = Path(f["path"]).read_text(encoding="utf-8", errors="replace")
                                    with st.expander("文件内容", expanded=True):
                                        st.text(content[:5000])
                                except Exception:
                                    st.error("无法读取文件")

    # ── Tab 3: Profile ──
    with tab3:
        profile = st.session_state.storage.load_profile()

        if profile:
            st.markdown(f"""
            <div class="profile-hero">
                <div class="profile-name">{profile.name or '候选人'}</div>
                <div class="profile-role">{profile.current_title or ''} · {profile.years_of_experience} 年经验</div>
            </div>
            """, unsafe_allow_html=True)

            c1, c2 = st.columns(2)

            with c1:
                skills_html = '<br>'.join(f'<span style="color:var(--ink);">• {s}</span>' for s in profile.core_skills) if profile.core_skills else '暂无'
                b2b_html = '<br>'.join(f'<span style="color:var(--ink);">• {d}</span>' for d in profile.b2b_domain_expertise) if profile.b2b_domain_expertise else '暂无'
                st.markdown(f"""
                <div class="editorial-card accent-left">
                    <h4>核心技能</h4>
                    <p style="font-size:0.9rem;line-height:1.8;">{skills_html}</p>
                    <h4 style="margin-top:1rem;">B端专长</h4>
                    <p style="font-size:0.9rem;line-height:1.8;">{b2b_html}</p>
                </div>
                """, unsafe_allow_html=True)

            with c2:
                achievements_html = '<br>'.join(f'<span style="color:var(--ink);">✅ {a}</span>' for a in profile.highlight_achievements) if profile.highlight_achievements else '暂无'
                weaknesses_html = '<br>'.join(f'<span style="color:var(--vermillion);">⚠️ {w}</span>' for w in profile.weak_areas) if profile.weak_areas else '暂无'
                st.markdown(f"""
                <div class="editorial-card">
                    <h4>亮点成就</h4>
                    <p style="font-size:0.9rem;line-height:1.8;">{achievements_html}</p>
                    <h4 style="margin-top:1rem;">需加强</h4>
                    <p style="font-size:0.9rem;line-height:1.8;">{weaknesses_html}</p>
                </div>
                """, unsafe_allow_html=True)

            # Projects
            if profile.key_projects:
                st.markdown("<br>", unsafe_allow_html=True)
                section_header("项目经验")
                for p in profile.key_projects:
                    metrics_str = "; ".join(p.get("metrics", []))
                    st.markdown(f"""
                    <div class="history-item">
                        <strong>{p['name']}</strong> — {p.get('role', '')}<br>
                        <span style="font-size:0.8rem;color:var(--ink-light);">{metrics_str}</span>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            empty_state("👤", "尚未生成候选人画像", "请先导入素材，然后点击下方按钮生成画像")

        if st.button("🔄 重新生成画像", type="primary", use_container_width=True):
            with st.spinner("综合分析素材中..."):
                output = capture_output(material_module, st.session_state.material, "profile", "")
            display_rich(output)
            st.rerun()

    # ── Tab 4: Obsidian ──
    with tab4:
        vault_path = st.session_state.get("vault_path", "")
        if not vault_path:
            empty_state("📒", "未配置 Obsidian Vault", "在 config.yaml 中设置 obsidian.vault_path")
        elif not Path(vault_path).exists():
            st.error(f"Vault 路径不存在: {vault_path}")
        else:
            obs = st.session_state.get("obsidian_connector")
            if obs:
                st.success(f"已连接: {vault_path}")

                obs_keyword = st.text_input("搜索 Obsidian", placeholder="输入关键词...", key="obsidian_search_input", label_visibility="collapsed")
                if obs_keyword:
                    results = obs.search(obs_keyword, max_results=15)
                    if results:
                        st.caption(f"找到 {len(results)} 个文件")
                        for i, f in enumerate(results, 1):
                            ext_icon = {".md": "📝", ".pdf": "📄", ".csv": "📊"}.get(f["ext"], "📎")
                            c1, c2 = st.columns([5, 1])
                            with c1:
                                st.markdown(f"{i}. {ext_icon} **{f['name']}** — *{f['dir']}*")
                            with c2:
                                if st.button("📥 导入", key=f"obs_import_{i}"):
                                    result = obs.import_to_material(f["path"])
                                    st.success(f"已导入: {f['name']}")
                                    st.rerun()
                            with st.expander(f"预览: {f['name']}"):
                                content = obs.read_file(f["path"], max_chars=3000)
                                if content:
                                    st.text(content[:3000])
                    else:
                        st.info("未找到匹配文件")

                with st.expander("📊 Vault 目录结构"):
                    try:
                        vault_files = obs._scan()
                        st.caption(f"共 {len(vault_files)} 个可索引文件")
                        dirs = {}
                        for f in vault_files:
                            d = f["dir"] or "(根目录)"
                            dirs[d] = dirs.get(d, 0) + 1
                        for d, count in sorted(dirs.items()):
                            st.markdown(f"- {d}: {count} 个文件")
                    except Exception as e:
                        st.error(f"扫描失败: {e}")
            else:
                st.warning("Obsidian 连接器未初始化")


# ─── Page: Prep ──────────────────────────────────────────

def page_prep():
    stylized_title("面试准备")

    # Target setup
    st.markdown("""
    <div class="setup-section">
        <p style="font-size:0.9rem;color:var(--ink-light);margin-bottom:0.5rem;">
            设定目标公司与岗位，基于你的素材库生成定制化学习材料与面试题预测
        </p>
    </div>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns([3, 1])
    with c1:
        target = st.text_input(
            "目标公司与岗位",
            value=st.session_state.prep_target,
            placeholder="如: 字节跳动 资深B端产品经理",
            key="prep_target_input",
            label_visibility="collapsed",
        )
    with c2:
        gen_btn = st.button("生成材料", type="primary", use_container_width=True, disabled=not target)

    if gen_btn and target:
        st.session_state.prep_target = target
        with st.spinner("正在生成定制学习材料..."):
            output = capture_output(prep_module, st.session_state.prep, "for", target)
        st.session_state.prep_chat_history.append({
            "role": "assistant",
            "content": output if output else "学习材料已生成",
        })
        st.rerun()

    # Chat interface
    if st.session_state.prep_chat_history:
        st.markdown("---")

        for msg in st.session_state.prep_chat_history:
            role = msg["role"]
            content = clean_rich(msg["content"])
            if role == "assistant":
                st.markdown(f"""
                <div class="interviewer-bubble">
                    <div class="bubble-speaker">面试准备助手</div>
                    {content}
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="candidate-bubble">
                    <div class="bubble-speaker">我</div>
                    {content}
                </div>
                """, unsafe_allow_html=True)

        # Clear button
        if st.button("清空对话", type="secondary"):
            st.session_state.prep_chat_history = []
            st.session_state.prep._conversation_history = []
            st.rerun()

    # Chat input
    question = st.chat_input("输入面试相关问题...", key="prep_chat_input")
    if question:
        st.session_state.prep_chat_history.append({"role": "user", "content": question})

        with st.spinner("思考中..."):
            prep = st.session_state.prep
            context = prep._build_context()

            system_path = Path(__file__).parent.parent / "prompts" / "prep_assistant.txt"
            system = system_path.read_text() if system_path.exists() else "你是B端产品面试准备助手"
            system = system.replace("{profile_summary}", context[:5000])
            system = system.replace("{material_summary}", context[:5000])
            system = system.replace("{search_results}", "")

            prep._conversation_history.append({"role": "user", "content": question})

            try:
                resp = chat(system=system, messages=prep._conversation_history[-10:], temperature=0.5)
            except Exception as e:
                resp = f"回答失败: {e}"

            prep._conversation_history.append({"role": "assistant", "content": resp})

        st.session_state.prep_chat_history.append({"role": "assistant", "content": resp})
        st.rerun()


# ─── Page: Mock ──────────────────────────────────────────

def page_mock():
    stylized_title("模拟面试")

    # ── Review state ──
    if st.session_state.show_review and not st.session_state.mock_started:
        mock = st.session_state.mock
        if mock.current_session and mock.current_session.status == "已完成":

            st.markdown("""
            <div class="profile-hero">
                <div class="profile-name">面试完成</div>
                <div class="profile-role">查看评估报告，了解表现</div>
            </div>
            """, unsafe_allow_html=True)

            c1, c2 = st.columns(2)
            with c1:
                if st.button("📊 生成评估报告", type="primary", use_container_width=True):
                    with st.spinner("评估中..."):
                        review_out = capture_output(mock_module, mock, "review", "")
                    display_rich(review_out)
                    st.session_state.show_review = False
            with c2:
                if st.button("🔄 开始新一轮", type="secondary", use_container_width=True):
                    st.session_state.mock = MockSkill(st.session_state.storage)
                    st.session_state.mock_started = False
                    st.session_state.mock_active = False
                    st.session_state.mock_chat_history = []
                    st.session_state.show_review = False
                    st.rerun()
            return

    # ── Setup phase ──
    if not st.session_state.mock_started:
        st.markdown("""
        <div class="setup-section">
            <p style="font-size:0.9rem;color:var(--ink-light);margin-bottom:0.5rem;">
                选择简历和目标岗位，AI 面试官将基于你的素材发起真实模拟面试。共 10 题，覆盖行为面试、产品 Sense、估算、策略等多类题型。
            </p>
        </div>
        """, unsafe_allow_html=True)

        index = st.session_state.storage.get_index()
        resumes = index.get("resumes", [])
        jds = index.get("jds", [])

        # Two-column setup
        sc1, sc2 = st.columns(2)

        with sc1:
            st.markdown("""
            <div class="setup-section">
                <h4 style="margin-top:0;">📄 选择简历</h4>
            </div>
            """, unsafe_allow_html=True)

            resume_source = st.radio(
                "简历来源",
                ["从素材库选择", "上传本地文件"],
                horizontal=True,
                key="mock_resume_source",
                label_visibility="collapsed",
            )
            selected_resume = None
            resume_entry = None

            if resume_source == "从素材库选择":
                if resumes:
                    resume_names = [r.get("file", r.get("title", "")) for r in resumes]
                    selected_resume = st.selectbox("素材库简历", resume_names, key="mock_resume_select", label_visibility="collapsed")
                else:
                    st.warning("素材库没有简历，请先导入或上传本地文件")
            else:
                uploaded_resume = st.file_uploader(
                    "上传简历",
                    type=["txt", "md", "pdf", "xlsx", "png", "jpg", "jpeg", "webp"],
                    key="mock_resume_uploader",
                )
                if uploaded_resume:
                    upload_dir = Path(tempfile.gettempdir()) / "interview_agent_uploads"
                    upload_dir.mkdir(exist_ok=True)
                    resume_tmp = upload_dir / f"mock_resume_{uploaded_resume.name}"
                    resume_tmp.write_bytes(uploaded_resume.read())
                    selected_resume = uploaded_resume.name
                    resume_entry = {"file": uploaded_resume.name, "path": str(resume_tmp)}

        with sc2:
            st.markdown("""
            <div class="setup-section">
                <h4 style="margin-top:0;">🎯 选择岗位 JD</h4>
            </div>
            """, unsafe_allow_html=True)

            jd_source = st.radio(
                "JD来源",
                ["从素材库选择", "上传本地文件"],
                horizontal=True,
                key="mock_jd_source",
                label_visibility="collapsed",
            )
            selected_jd = None
            jd_entry = None

            if jd_source == "从素材库选择":
                if jds:
                    jd_names = [j.get("file", j.get("title", "")) for j in jds]
                    selected_jd = st.selectbox("素材库 JD", jd_names, key="mock_jd_select", label_visibility="collapsed")
                else:
                    st.warning("素材库没有 JD，请先导入或上传本地文件")
            else:
                uploaded_jd = st.file_uploader(
                    "上传 JD",
                    type=["txt", "md", "pdf", "xlsx", "png", "jpg", "jpeg", "webp"],
                    key="mock_jd_uploader",
                )
                if uploaded_jd:
                    upload_dir = Path(tempfile.gettempdir()) / "interview_agent_uploads"
                    upload_dir.mkdir(exist_ok=True)
                    jd_tmp = upload_dir / f"mock_jd_{uploaded_jd.name}"
                    jd_tmp.write_bytes(uploaded_jd.read())
                    selected_jd = uploaded_jd.name
                    jd_entry = {"file": uploaded_jd.name, "path": str(jd_tmp)}

        can_start = bool(selected_resume and selected_jd)

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🎬 开始面试", type="primary", use_container_width=True, disabled=not can_start):
            if resume_source == "从素材库选择":
                resume_entry = next((r for r in resumes if r.get("file") == selected_resume), None)
            if jd_source == "从素材库选择":
                jd_entry = next((j for j in jds if j.get("file") == selected_jd), None)

            if resume_entry and jd_entry:
                resume_path = resume_entry.get("path", "")
                jd_path = jd_entry.get("path", "")

                if jd_source == "从素材库选择":
                    jd_title = jd_entry.get("title", "")
                    title_parts = jd_title.split(maxsplit=1)
                    jd_company = title_parts[0] if title_parts else ""
                    jd_position = title_parts[1] if len(title_parts) > 1 else jd_title
                else:
                    jd_name = os.path.splitext(selected_jd)[0]
                    jd_company = jd_name
                    jd_position = jd_name

                mock = st.session_state.mock
                mock._selected_resume_path = resume_path
                mock._selected_jd_path = jd_path

                with st.spinner("面试官正在准备..."):
                    output = capture_output(mock_module, mock, "start", f"{jd_company} {jd_position}")

                cleaned = clean_rich(output)
                st.session_state.mock_chat_history = [
                    {"role": "assistant", "content": cleaned or output}
                ]
                st.session_state.mock_started = True
                st.session_state.mock_active = True
                st.rerun()

        # History
        with st.expander("📋 历史面试记录"):
            sessions = st.session_state.storage.list_sessions()
            if sessions:
                for s in sessions[:5]:
                    score = s.get("overall_score", 0)
                    score_str = f"{score}/10" if score else "未评分"
                    st.markdown(
                        f"- {s.get('company', '?')} — {s.get('position', '?')} "
                        f"({(s.get('started_at', '') or '')[:10]}) — {score_str}"
                    )
            else:
                st.caption("暂无历史记录")
        return

    # ── Active interview ──
    mock = st.session_state.mock

    if mock.current_session:
        sess = mock.current_session
        # Interview header bar
        st.markdown(f"""
        <div class="interview-header">
            <span>🏢 <strong>{sess.company}</strong> — {sess.position}</span>
            <span class="ih-stat">已回答 <strong>{len(sess.answers)}</strong> 题</span>
            <span class="ih-stat">状态 <strong>{sess.status}</strong></span>
        </div>
        """, unsafe_allow_html=True)

    # Chat history with styled bubbles
    for msg in st.session_state.mock_chat_history:
        role = msg["role"]
        content = msg["content"]
        content = clean_rich(content)
        # Strip leading emoji lines from assistant messages
        content = re.sub(r'^[🎙🎯💡📊📋]\S*\s*[^\n]*?\n', '', content)
        if not content:
            continue

        if role == "assistant":
            st.markdown(f"""
            <div class="interviewer-bubble fade-up">
                <div class="bubble-speaker">面试官</div>
                {content}
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="candidate-bubble fade-up">
                <div class="bubble-speaker">候选人</div>
                {content}
            </div>
            """, unsafe_allow_html=True)

    # Action buttons
    c1, c2 = st.columns(2)
    with c1:
        if st.button("💡 请求提示", use_container_width=True, type="secondary"):
            with st.spinner():
                hint_out = capture_output(mock_module, mock, "hint", "")
            cleaned = clean_rich(hint_out)
            st.session_state.mock_chat_history.append({"role": "assistant", "content": f"💡 **提示**:\n\n{cleaned}"})
            st.rerun()
    with c2:
        if st.button("⏹ 结束面试", use_container_width=True, type="secondary"):
            mock.run("end", "")
            st.session_state.mock_started = False
            st.session_state.mock_active = False
            st.session_state.show_review = True
            st.rerun()

    # Answer input
    answer = st.chat_input("输入你的回答...", key="mock_answer_input")
    if answer:
        st.session_state.mock_chat_history.append({"role": "user", "content": answer})

        with st.spinner("面试官思考中..."):
            interviewer_resp = capture_output(mock_module, mock, "answer", answer)

        cleaned = clean_rich(interviewer_resp)
        st.session_state.mock_chat_history.append({"role": "assistant", "content": cleaned or interviewer_resp})

        if mock.current_session and len(mock.current_session.answers) >= 10:
            st.session_state.mock_started = False
            st.session_state.mock_active = False
            st.session_state.show_review = True
            st.warning("已达最大题数 (10题)，面试自动结束。")

        st.rerun()


# ─── Sidebar ─────────────────────────────────────────────

def sidebar():
    with st.sidebar:
        st.markdown("## B端PM\n## 面试助手")

        profile = st.session_state.storage.load_profile()
        if profile:
            st.markdown("---")
            st.caption(f"👤 {profile.name}")
            st.caption(f"💼 {profile.current_title}")

        st.markdown("---")
        st.caption("v1.3 · Streamlit")


# ─── Main ────────────────────────────────────────────────

def main():
    init_session()
    render_nav()

    page_map = {
        "首页": page_home,
        "素材库": page_material,
        "面试准备": page_prep,
        "模拟面试": page_mock,
    }

    page_fn = page_map.get(st.session_state.page, page_home)
    page_fn()

    sidebar()


if __name__ == "__main__":
    main()
