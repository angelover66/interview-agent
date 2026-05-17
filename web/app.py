"""Streamlit Web UI for Interview Agent."""
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
# This must happen BEFORE importing core modules
try:
    for key, value in st.secrets.items():
        if key not in os.environ:
            os.environ[key] = value
except Exception:
    pass  # st.secrets not available in non-Streamlit context

from rich.console import Console

from core.storage import StorageManager
from core.llm import chat, chat_json
from core.models import MockSession, MockQuestion, MockAnswer
from skills.material import MaterialSkill
from skills.prep import PrepSkill
from skills.mock import MockSkill
from connectors.obsidian import ObsidianConnector

# Import skill modules for console capture
import skills.material as material_module
import skills.prep as prep_module
import skills.mock as mock_module

from web.ui import rich_to_html, rich_to_text

# ─── Page config ─────────────────────────────────────────

st.set_page_config(
    page_title="B端产品经理面试助手",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS tweaks ───────────────────────────────────────────

st.markdown("""
<style>
    .stChatMessage { padding: 0.5rem 1rem; }
    .interviewer-msg { border-left: 3px solid #e74c3c; }
    .candidate-msg { border-left: 3px solid #3498db; }
    .score-badge { font-size: 2rem; font-weight: bold; }
    .dim-table td { padding: 0.3rem 0.8rem; }
</style>
""", unsafe_allow_html=True)

# ─── Session state init ──────────────────────────────────

def init_session():
    """Initialize or restore session state."""
    if "storage" not in st.session_state:
        st.session_state.storage = StorageManager(base_dir="./data")

        # 读取 Obsidian 配置
        config_path = Path(__file__).parent.parent / "config.yaml"
        config = yaml.safe_load(config_path.read_text()) if config_path.exists() else {}
        vault_path = config.get("obsidian", {}).get("vault_path", "")

        obsidian_connector = None
        if vault_path and Path(vault_path).exists():
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

        # Current page
        st.session_state.page = "素材库"


# ─── Console capture helper ───────────────────────────────

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

    # Prefer non-empty return value over captured console output
    if result and result.strip():
        return result
    return captured


def display_rich_text(text: str):
    """Display text that may contain rich markup, converting to HTML."""
    if not text or not text.strip():
        return
    # Strip box-drawing characters from Panel/Table/Tree borders
    cleaned = re.sub(r'[╭╮╰╯│├└┬┴┼═─━]', '', text)
    cleaned = cleaned.strip()
    if not cleaned:
        return
    # Convert remaining rich tags to HTML, render as markdown
    html = rich_to_html(cleaned)
    st.markdown(html, unsafe_allow_html=True)


# ─── Page: 素材库 ─────────────────────────────────────────

def page_material():
    st.header("📂 素材库管理")

    tab1, tab2, tab3, tab4 = st.tabs(["导入素材", "素材列表", "候选人画像", "Obsidian"])

    # ── Tab 1: 导入 ──
    with tab1:
        st.subheader("导入素材")
        uploaded = st.file_uploader(
            "上传简历 / 项目文档 / JD（支持 .txt / .md / .pdf）",
            type=["txt", "md", "pdf"],
            key="material_uploader",
        )
        if uploaded:
            # Save to temp dir preserving original filename
            upload_dir = Path(tempfile.gettempdir()) / "interview_agent_uploads"
            upload_dir.mkdir(exist_ok=True)
            tmp_path = upload_dir / uploaded.name
            tmp_path.write_bytes(uploaded.read())

            with st.spinner("正在提取结构化信息..."):
                output = capture_output(material_module, st.session_state.material, "import", str(tmp_path))

            tmp_path.unlink(missing_ok=True)
            display_rich_text(output)
            st.success("素材已入库")

    # ── Tab 2: 列表 ──
    with tab2:
        st.subheader("素材列表")

        files = st.session_state.storage.list_raw_files()
        index = st.session_state.storage.get_index()

        if not files:
            st.info("素材库为空，请先导入素材")
        else:
            # Search box
            keyword = st.text_input("搜索素材", key="material_search")

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
                    st.caption("无精确匹配")

            for f in display_files:
                cat_emoji = {"resumes": "📄", "projects": "📁", "jds": "🎯"}.get(f["category"], "📎")
                col_a, col_b, col_c = st.columns([4, 1, 1])
                with col_a:
                    st.markdown(f"{cat_emoji} **{f['name']}** ({f['size']//1024}KB) — *{f['category']}*")
                with col_b:
                    # View content button
                    view_key = f"view_{f['path']}"
                    if st.button("📖 查看", key=view_key):
                        try:
                            content = Path(f["path"]).read_text(encoding="utf-8", errors="replace")
                            st.session_state[f"viewing_{view_key}"] = not st.session_state.get(f"viewing_{view_key}", False)
                        except Exception:
                            st.error("无法读取文件")
                with col_c:
                    # Delete button
                    del_key = f"del_{f['name']}"
                    if st.button("🗑 删除", key=del_key):
                        st.session_state.material.run("delete", f["name"])
                        st.rerun()

                # Show content if toggled
                if st.session_state.get(f"viewing_{view_key}", False):
                    try:
                        content = Path(f["path"]).read_text(encoding="utf-8", errors="replace")
                        with st.expander("文件内容", expanded=True):
                            st.text(content[:5000])
                    except Exception:
                        st.error("无法读取文件")

    # ── Tab 3: 画像 ──
    with tab3:
        st.subheader("候选人画像")
        profile = st.session_state.storage.load_profile()

        if profile:
            # Profile card
            col_a, col_b = st.columns([1, 2])
            with col_a:
                st.metric("经验年限", f"{profile.years_of_experience} 年")
                st.markdown("**核心技能**")
                for s in profile.core_skills:
                    st.markdown(f"- {s}")
                st.markdown("**B端专长**")
                for d in profile.b2b_domain_expertise:
                    st.markdown(f"- {d}")

            with col_b:
                st.markdown(f"### {profile.name or '未知'}")
                st.caption(f"当前职位: {profile.current_title}")
                st.caption(f"目标岗位: {', '.join(profile.target_positions)}")
                st.markdown(f"**职业简介**: {profile.career_summary}")

                st.markdown("**亮点成就**")
                for a in profile.highlight_achievements:
                    st.markdown(f"- ✅ {a}")

                st.markdown("**需加强**")
                for w in profile.weak_areas:
                    st.markdown(f"- ⚠️ {w}")

                st.markdown("**项目经验**")
                for p in profile.key_projects:
                    metrics_str = "; ".join(p.get("metrics", []))
                    st.markdown(f"- **{p['name']}** ({p.get('role', '')}): {metrics_str}")
        else:
            st.warning("尚未生成候选人画像。请先导入素材，然后点击下方按钮生成。")

        if st.button("🔄 重新生成画像", use_container_width=True):
            with st.spinner("综合分析素材中..."):
                output = capture_output(material_module, st.session_state.material, "profile", "")
            display_rich_text(output)
            st.rerun()

    # ── Tab 4: Obsidian ──
    with tab4:
        st.subheader("📒 Obsidian 知识库")

        vault_path = st.session_state.get("vault_path", "")
        if not vault_path:
            st.warning("未配置 Obsidian Vault 路径，请在 config.yaml 中设置 obsidian.vault_path")
        elif not Path(vault_path).exists():
            st.error(f"Vault 路径不存在: {vault_path}")
        else:
            obs = st.session_state.get("obsidian_connector")
            if obs:
                st.success(f"已连接: {vault_path}")

                # Search
                obs_keyword = st.text_input("搜索 Obsidian", key="obsidian_search_input")
                if obs_keyword:
                    results = obs.search(obs_keyword, max_results=15)
                    if results:
                        st.caption(f"找到 {len(results)} 个文件")
                        for i, f in enumerate(results, 1):
                            col_a, col_b = st.columns([4, 1])
                            ext_icon = {".md": "📝", ".pdf": "📄", ".csv": "📊"}.get(f["ext"], "📎")
                            with col_a:
                                st.markdown(f"{i}. {ext_icon} **{f['name']}** — *{f['dir']}*")
                            with col_b:
                                if st.button("📥 导入", key=f"obs_import_{i}"):
                                    result = obs.import_to_material(f["path"])
                                    st.success(f"已导入: {f['name']}")
                                    st.rerun()
                            # Preview
                            with st.expander(f"预览: {f['name']}"):
                                content = obs.read_file(f["path"], max_chars=3000)
                                if content:
                                    st.text(content[:3000])
                    else:
                        st.info("未找到匹配文件")

                # Vault stats
                with st.expander("📊 Vault 目录结构"):
                    try:
                        files = obs._scan()
                        st.caption(f"共 {len(files)} 个可索引文件")
                        dirs = {}
                        for f in files:
                            d = f["dir"] or "(根目录)"
                            dirs[d] = dirs.get(d, 0) + 1
                        for d, count in sorted(dirs.items()):
                            st.markdown(f"- {d}: {count} 个文件")
                    except Exception as e:
                        st.error(f"扫描失败: {e}")
            else:
                st.warning("Obsidian 连接器未初始化")


# ─── Page: 面试准备 ────────────────────────────────────────

def page_prep():
    st.header("📖 面试准备")

    # Target setup
    col1, col2 = st.columns([3, 1])
    with col1:
        target = st.text_input(
            "目标公司和岗位",
            value=st.session_state.prep_target,
            placeholder="如: 字节跳动 资深B端产品经理",
            key="prep_target_input",
        )
    with col2:
        gen_btn = st.button("生成学习材料", use_container_width=True, disabled=not target)

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
    st.markdown("---")
    st.subheader("💬 准备问答")

    # Display chat history
    for msg in st.session_state.prep_chat_history:
        role = "assistant" if msg["role"] == "assistant" else "user"
        with st.chat_message(role):
            if role == "assistant":
                # Clean and display as markdown
                cleaned = re.sub(r'[╭╮╰╯│├└┬┴┼═─━]', '', msg["content"])
                st.markdown(rich_to_html(cleaned), unsafe_allow_html=True)
            else:
                st.markdown(msg["content"])

    # Chat input
    question = st.chat_input("输入面试相关问题...", key="prep_chat_input")
    if question:
        st.session_state.prep_chat_history.append({"role": "user", "content": question})

        with st.spinner("思考中..."):
            # Call prep._cmd_ask directly for cleaner output
            prep = st.session_state.prep
            context = prep._build_context()
            profile = st.session_state.storage.load_profile()

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

    # Clear button
    if st.session_state.prep_chat_history:
        if st.button("清空对话"):
            st.session_state.prep_chat_history = []
            st.session_state.prep._conversation_history = []
            st.rerun()


# ─── Page: 模拟面试 ────────────────────────────────────────

def page_mock():
    st.header("🎯 模拟面试")

    # ── State: Show review of completed session ──
    if st.session_state.show_review and not st.session_state.mock_started:
        mock = st.session_state.mock
        if mock.current_session and mock.current_session.status == "已完成":
            st.info(f"🏢 {mock.current_session.company} — {mock.current_session.position} 面试已完成")

            if st.button("📊 生成评估报告", type="primary", use_container_width=True):
                with st.spinner("评估中..."):
                    review_out = capture_output(mock_module, mock, "review", "")
                display_rich_text(review_out)
                st.session_state.show_review = False

            if st.button("🔄 开始新一轮面试", use_container_width=True):
                st.session_state.mock = MockSkill(st.session_state.storage)
                st.session_state.mock_started = False
                st.session_state.mock_active = False
                st.session_state.mock_chat_history = []
                st.session_state.show_review = False
                st.rerun()
            return  # Don't show setup form while review is pending

    # ── State: Setup form ──
    if not st.session_state.mock_started:
        st.markdown("#### 开始一场模拟面试")

        # 从素材库获取可用的简历和 JD
        index = st.session_state.storage.get_index()
        resumes = index.get("resumes", [])
        jds = index.get("jds", [])

        col1, col2 = st.columns(2)
        with col1:
            if resumes:
                resume_names = [r.get("file", r.get("title", "")) for r in resumes]
                selected_resume = st.selectbox("选择简历", resume_names, key="mock_resume_select")
            else:
                st.warning("素材库中没有简历，请先在素材库上传简历")
                selected_resume = None

        with col2:
            if jds:
                jd_names = [j.get("file", j.get("title", "")) for j in jds]
                selected_jd = st.selectbox("选择目标岗位 JD", jd_names, key="mock_jd_select")
            else:
                st.warning("素材库中没有 JD，请先在素材库上传 JD")
                selected_jd = None

        can_start = selected_resume and selected_jd

        if st.button("🎬 开始面试", type="primary", use_container_width=True, disabled=not can_start):
            # 读取选中文件和提取信息
            resume_entry = next((r for r in resumes if r.get("file") == selected_resume), None)
            jd_entry = next((j for j in jds if j.get("file") == selected_jd), None)

            if resume_entry and jd_entry:
                jd_path = jd_entry.get("path", "")
                jd_title = jd_entry.get("title", "")
                # 从 JD 标题拆分公司/岗位
                title_parts = jd_title.split(maxsplit=1)
                jd_company = title_parts[0] if title_parts else ""
                jd_position = title_parts[1] if len(title_parts) > 1 else jd_title

                # 将选中文件的路径存储到 mock skill 中
                mock = st.session_state.mock
                mock._selected_resume_path = resume_entry.get("path", "")
                mock._selected_jd_path = jd_path

                with st.spinner("面试官正在准备..."):
                    output = capture_output(mock_module, mock, "start", f"{jd_company} {jd_position}")

                cleaned = re.sub(r'[╭╮╰╯│├└┬┴┼═─━]', '', output).strip()

                st.session_state.mock_chat_history = [
                    {"role": "assistant", "content": cleaned or output}
                ]
                st.session_state.mock_started = True
                st.session_state.mock_active = True
                st.rerun()

        # Previous sessions
        with st.expander("📋 历史模拟面试"):
            sessions = st.session_state.storage.list_sessions()
            if sessions:
                for s in sessions[:5]:
                    score_str = f"{s.get('overall_score', 0)}/10" if s.get("overall_score") else "未评分"
                    st.markdown(
                        f"- {s.get('company', '?')} — {s.get('position', '?')} "
                        f"({s.get('started_at', '')[:10]}) — {score_str}"
                    )
            else:
                st.caption("暂无历史记录")
        return

    # ── State: Active interview ──
    mock = st.session_state.mock

    # Header
    if mock.current_session:
        sess = mock.current_session
        col_a, col_b, col_c, col_d = st.columns([2, 1, 1, 1])
        with col_a:
            st.caption(f"🏢 {sess.company} — {sess.position}")
        with col_b:
            st.caption(f"已回答: {len(sess.answers)} 题")
        with col_c:
            st.caption(f"状态: {sess.status}")
        with col_d:
            if st.button("⏹ 结束", key="end_interview"):
                mock.run("end", "")
                st.session_state.mock_started = False
                st.session_state.mock_active = False
                st.session_state.show_review = True
                st.rerun()

    st.markdown("---")

    # Chat display
    for msg in st.session_state.mock_chat_history:
        role = msg["role"]
        with st.chat_message(role):
            content = msg["content"]
            content = re.sub(r'[╭╮╰╯│├└┬┴┼═─━]', '', content).strip()
            content = re.sub(r'^[🎙🎯💡📊📋]\S*\s*[^\n]*?\n', '', content)
            if content:
                st.markdown(rich_to_html(content), unsafe_allow_html=True)

    # Action buttons
    col1, col2 = st.columns(2)
    with col1:
        if st.button("💡 请求提示", use_container_width=True):
            with st.spinner():
                hint_out = capture_output(mock_module, mock, "hint", "")
            cleaned = re.sub(r'[╭╮╰╯│├└┬┴┼═─━]', '', hint_out).strip()
            st.session_state.mock_chat_history.append({"role": "assistant", "content": f"💡 **提示**:\n\n{cleaned}"})
            st.rerun()
    with col2:
        if st.button("🔄 重新开始", use_container_width=True):
            st.session_state.mock = MockSkill(st.session_state.storage)
            st.session_state.mock_started = False
            st.session_state.mock_active = False
            st.session_state.mock_chat_history = []
            st.session_state.show_review = False
            st.rerun()

    # Chat input
    answer = st.chat_input("输入你的回答...", key="mock_answer_input")
    if answer:
        st.session_state.mock_chat_history.append({"role": "user", "content": answer})

        with st.spinner("面试官思考中..."):
            interviewer_resp = capture_output(mock_module, mock, "answer", answer)

        cleaned = re.sub(r'[╭╮╰╯│├└┬┴┼═─━]', '', interviewer_resp).strip()
        st.session_state.mock_chat_history.append({"role": "assistant", "content": cleaned or interviewer_resp})

        # Max questions reached?
        if mock.current_session and len(mock.current_session.answers) >= 10:
            st.session_state.mock_started = False
            st.session_state.mock_active = False
            st.session_state.show_review = True
            st.warning("已达最大题数 (10题)，面试自动结束。")

        st.rerun()


# ─── Sidebar ──────────────────────────────────────────────

def sidebar():
    with st.sidebar:
        st.markdown("## 🎯 B端产品经理\n## 面试助手")
        st.markdown("---")

        # Page navigation
        pages = {
            "📖 面试准备": "面试准备",
            "🎯 模拟面试": "模拟面试",
            "📂 素材库": "素材库",
        }

        current_label = next((k for k, v in pages.items() if v == st.session_state.page), "📖 面试准备")

        selected_label = st.radio(
            "导航",
            list(pages.keys()),
            index=list(pages.keys()).index(current_label),
            label_visibility="collapsed",
        )
        st.session_state.page = pages[selected_label]

        st.markdown("---")

        profile = st.session_state.storage.load_profile()
        if profile:
            st.caption(f"👤 {profile.name}")
            st.caption(f"💼 {profile.current_title}")

        st.markdown("---")
        st.caption("v1.0 | Streamlit Web UI")


# ─── Main ─────────────────────────────────────────────────

def main():
    init_session()

    sidebar()

    page_map = {
        "素材库": page_material,
        "面试准备": page_prep,
        "模拟面试": page_mock,
    }

    page_fn = page_map.get(st.session_state.page, page_prep)
    page_fn()


if __name__ == "__main__":
    main()
