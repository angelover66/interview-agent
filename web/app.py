"""Streamlit Web UI for Interview Agent — 简洁版左侧导航布局."""
from __future__ import annotations
import sys
import re
import os
import tempfile
from pathlib import Path
from io import StringIO

sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
import streamlit as st

try:
    for key, value in st.secrets.items():
        if key not in os.environ:
            os.environ[key] = value
except Exception:
    pass

from rich.console import Console

from core.storage import StorageManager
from core.llm import chat
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

from web.ui import rich_to_html
from web.styles import THEME_CSS

# ─── Page config ─────────────────────────────────────────

st.set_page_config(
    page_title="B端产品经理面试助手",
    page_icon="🎯",
    layout="wide",
)

# ─── CSS injection ──────────────────────────────────────

st.markdown(f"<style>{THEME_CSS}</style>", unsafe_allow_html=True)

# ─── Session state init ──────────────────────────────────

def init_session():
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

        st.session_state.mock_active = False
        st.session_state.mock_chat_history = []
        st.session_state.mock_started = False
        st.session_state.show_review = False

        st.session_state.prep_chat_history = []
        st.session_state.prep_target = ""

        st.session_state.page = "首页"


# ─── Helpers ──────────────────────────────────────────────

def capture_output(skill_module, skill_instance, action: str, args: str = "") -> str:
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
    if not text or not text.strip():
        return ""
    cleaned = re.sub(r'[╭╮╰╯│├└┬┴┼═─━]', '', text).strip()
    return rich_to_html(cleaned)


def display_rich(text: str):
    cleaned = clean_rich(text)
    if cleaned:
        st.markdown(cleaned, unsafe_allow_html=True)


def chat_bubble(role: str, content: str) -> str:
    """Render a simple chat bubble."""
    if role == "assistant":
        return f"""<div class="interviewer-bubble">
            <div class="bubble-speaker">面试官</div>
            {content}
        </div>"""
    else:
        return f"""<div class="candidate-bubble">
            <div class="bubble-speaker">候选人</div>
            {content}
        </div>"""


# ─── Sidebar Navigation ──────────────────────────────────

def render_sidebar():
    with st.sidebar:
        st.markdown("## 🎯 面试助手")
        st.caption("B端产品经理一站式准备")

        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

        pages = ["🏠  首页", "📂  素材库", "📖  面试准备", "🎯  模拟面试"]
        page_map = {
            "🏠  首页": "首页",
            "📂  素材库": "素材库",
            "📖  面试准备": "面试准备",
            "🎯  模拟面试": "模拟面试",
        }

        current_label = next(
            (k for k, v in page_map.items() if v == st.session_state.page),
            "🏠  首页",
        )
        idx = pages.index(current_label)

        selected = st.radio(
            "导航",
            pages,
            index=idx,
            label_visibility="collapsed",
            key="sidebar_nav",
        )
        page = page_map[selected]
        if page != st.session_state.page:
            st.session_state.page = page
            st.rerun()

        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

        profile = st.session_state.storage.load_profile()
        if profile:
            st.caption(f"👤 {profile.name or '候选人'}")
            st.caption(f"💼 {profile.current_title or ''}")

        st.caption("v1.3")


# ─── Page: Home ───────────────────────────────────────────

def page_home():
    st.header("首页")

    profile = st.session_state.storage.load_profile()

    if profile:
        st.markdown(f"""
        <div class="simple-card">
            <h3>{profile.name or '候选人'}</h3>
            <p style="color:var(--text-secondary);margin:0;">
                {profile.current_title or ''} · {profile.years_of_experience} 年经验
            </p>
            <p style="color:var(--text-secondary);margin:0.25rem 0 0 0;">
                目标：{', '.join(profile.target_positions) if profile.target_positions else '未设定'}
            </p>
        </div>
        """, unsafe_allow_html=True)

        # Core skills summary
        if profile.core_skills:
            st.markdown(f"**核心技能**：{' · '.join(profile.core_skills[:6])}")
        if profile.highlight_achievements:
            st.markdown(f"**亮点**：{profile.highlight_achievements[0]}")
    else:
        st.info("尚未生成候选人画像。请先到素材库上传简历，然后生成画像。")

    st.markdown("---")

    st.subheader("快速开始")
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("📂  导入素材", use_container_width=True):
            st.session_state.page = "素材库"
            st.rerun()
    with c2:
        if st.button("📖  面试准备", use_container_width=True):
            st.session_state.page = "面试准备"
            st.rerun()
    with c3:
        if st.button("🎯  模拟面试", use_container_width=True):
            st.session_state.page = "模拟面试"
            st.rerun()


# ─── Page: Material ───────────────────────────────────────

def page_material():
    st.header("素材库")

    tab1, tab2, tab3, tab4 = st.tabs(["导入", "浏览", "画像", "Obsidian"])

    # ── Tab 1: Import ──
    with tab1:
        st.caption("支持 .txt / .md / .pdf / .xlsx / .xls / .png / .jpg / .webp")
        uploaded = st.file_uploader(
            "上传素材",
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
            st.info("素材库为空，请先导入")
        else:
            keyword = st.text_input(
                "搜索",
                placeholder="输入关键词...",
                key="material_search",
                label_visibility="collapsed",
            )
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

            for f in display_files:
                cat_emoji = {"resumes": "📄", "projects": "📁", "jds": "🎯", "images": "🖼️"}.get(f.get("category", ""), "📎")
                is_image = f.get("category") == "images" or f.get("name", "").lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif"))
                size_kb = f.get("size", 0) // 1024

                c1, c2, c3 = st.columns([5, 1, 1])
                with c1:
                    st.markdown(f"{cat_emoji} **{f['name']}**  `{size_kb}KB`")
                with c2:
                    view_key = f"view_{f['path']}"
                    label = "🖼️" if is_image else "📖"
                    if st.button(label, key=view_key):
                        st.session_state[f"show_{view_key}"] = not st.session_state.get(f"show_{view_key}", False)
                with c3:
                    if st.button("🗑", key=f"del_{f['name']}"):
                        st.session_state.material.run("delete", f["name"])
                        st.rerun()

                if st.session_state.get(f"show_{view_key}", False):
                    if is_image:
                        try:
                            st.image(f["path"], caption=f["name"], use_container_width=True)
                        except Exception:
                            st.error("无法加载")
                    else:
                        try:
                            content = Path(f["path"]).read_text(encoding="utf-8", errors="replace")
                            st.text(content[:3000])
                        except Exception:
                            st.error("无法读取")

    # ── Tab 3: Profile ──
    with tab3:
        profile = st.session_state.storage.load_profile()
        if profile:
            st.markdown(f"### {profile.name or '候选人'}")
            st.caption(f"{profile.current_title or ''} · {profile.years_of_experience} 年经验")

            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**核心技能**")
                for s in profile.core_skills:
                    st.markdown(f"- {s}")
                st.markdown("**B端专长**")
                for d in profile.b2b_domain_expertise:
                    st.markdown(f"- {d}")
            with c2:
                st.markdown("**亮点成就**")
                for a in profile.highlight_achievements:
                    st.markdown(f"- ✅ {a}")
                st.markdown("**需加强**")
                for w in profile.weak_areas:
                    st.markdown(f"- ⚠️ {w}")

            if profile.key_projects:
                st.markdown("**项目经验**")
                for p in profile.key_projects:
                    metrics_str = "; ".join(p.get("metrics", []))
                    st.markdown(f"- **{p['name']}** ({p.get('role', '')}): {metrics_str}")
        else:
            st.info("尚未生成候选人画像，请先导入素材后生成。")

        if st.button("🔄 重新生成画像", type="primary", use_container_width=True):
            with st.spinner("分析中..."):
                output = capture_output(material_module, st.session_state.material, "profile", "")
            display_rich(output)
            st.rerun()

    # ── Tab 4: Obsidian ──
    with tab4:
        vault_path = st.session_state.get("vault_path", "")
        if not vault_path:
            st.info("未配置 Obsidian Vault，请在 config.yaml 中设置")
        elif not Path(vault_path).exists():
            st.error(f"路径不存在: {vault_path}")
        else:
            obs = st.session_state.get("obsidian_connector")
            if obs:
                st.success(f"已连接: {vault_path}")
                obs_keyword = st.text_input(
                    "搜索 Obsidian",
                    placeholder="输入关键词...",
                    key="obsidian_search",
                    label_visibility="collapsed",
                )
                if obs_keyword:
                    results = obs.search(obs_keyword, max_results=15)
                    if results:
                        for i, f in enumerate(results, 1):
                            ext_icon = {".md": "📝", ".pdf": "📄", ".csv": "📊"}.get(f["ext"], "📎")
                            c1, c2 = st.columns([5, 1])
                            with c1:
                                st.markdown(f"{i}. {ext_icon} **{f['name']}** — *{f['dir']}*")
                            with c2:
                                if st.button("📥", key=f"obs_import_{i}"):
                                    obs.import_to_material(f["path"])
                                    st.success(f"已导入: {f['name']}")
                                    st.rerun()
                            with st.expander(f"预览: {f['name']}"):
                                content = obs.read_file(f["path"], max_chars=3000)
                                if content:
                                    st.text(content[:3000])
                    else:
                        st.info("未找到匹配文件")

                with st.expander("Vault 目录结构"):
                    try:
                        vault_files = obs._scan()
                        st.caption(f"共 {len(vault_files)} 个文件")
                        dirs = {}
                        for f in vault_files:
                            d = f["dir"] or "(根目录)"
                            dirs[d] = dirs.get(d, 0) + 1
                        for d, count in sorted(dirs.items()):
                            st.markdown(f"- {d}: {count} 个")
                    except Exception as e:
                        st.error(f"扫描失败: {e}")
            else:
                st.warning("Obsidian 连接器未初始化")


# ─── Page: Prep ──────────────────────────────────────────

def page_prep():
    st.header("面试准备")

    c1, c2 = st.columns([3, 1])
    with c1:
        target = st.text_input(
            "目标公司与岗位",
            value=st.session_state.prep_target,
            placeholder="如: 字节跳动 资深B端产品经理",
            key="prep_target_input",
        )
    with c2:
        if st.button("生成材料", type="primary", use_container_width=True, disabled=not target):
            if target:
                st.session_state.prep_target = target
                with st.spinner("生成中..."):
                    output = capture_output(prep_module, st.session_state.prep, "for", target)
                st.session_state.prep_chat_history.append({
                    "role": "assistant",
                    "content": output if output else "学习材料已生成",
                })
                st.rerun()

    if st.session_state.prep_chat_history:
        st.markdown("---")
        for msg in st.session_state.prep_chat_history:
            content = clean_rich(msg["content"])
            if msg["role"] == "assistant":
                st.markdown(f"""<div class="interviewer-bubble">
                    <div class="bubble-speaker">助手</div>{content}
                </div>""", unsafe_allow_html=True)
            else:
                st.markdown(f"""<div class="candidate-bubble">
                    <div class="bubble-speaker">我</div>{content}
                </div>""", unsafe_allow_html=True)

        if st.button("清空对话", type="secondary"):
            st.session_state.prep_chat_history = []
            st.session_state.prep._conversation_history = []
            st.rerun()

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
    st.header("模拟面试")

    # ── Review state ──
    if st.session_state.show_review and not st.session_state.mock_started:
        mock = st.session_state.mock
        if mock.current_session and mock.current_session.status == "已完成":
            st.success("面试已完成")
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
        st.caption("选择简历和目标岗位，AI 面试官将基于你的素材进行模拟面试（共 10 题）")

        index = st.session_state.storage.get_index()
        resumes = index.get("resumes", [])
        jds = index.get("jds", [])

        c1, c2 = st.columns(2)

        with c1:
            st.markdown("**📄 选择简历**")
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
                    selected_resume = st.selectbox("简历", resume_names, key="mock_resume_select", label_visibility="collapsed")
                else:
                    st.warning("素材库没有简历")
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

        with c2:
            st.markdown("**🎯 选择 JD**")
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
                    selected_jd = st.selectbox("JD", jd_names, key="mock_jd_select", label_visibility="collapsed")
                else:
                    st.warning("素材库没有 JD")
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

                with st.spinner("面试官准备中..."):
                    output = capture_output(mock_module, mock, "start", f"{jd_company} {jd_position}")

                cleaned = clean_rich(output)
                st.session_state.mock_chat_history = [
                    {"role": "assistant", "content": cleaned or output}
                ]
                st.session_state.mock_started = True
                st.session_state.mock_active = True
                st.rerun()

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
                st.caption("暂无记录")
        return

    # ── Active interview ──
    mock = st.session_state.mock

    if mock.current_session:
        sess = mock.current_session
        st.markdown(f"""
        <div class="interview-bar">
            🏢 <strong>{sess.company}</strong> — {sess.position} &nbsp;|&nbsp;
            已答 <strong>{len(sess.answers)}</strong> 题 &nbsp;|&nbsp;
            {sess.status}
        </div>
        """, unsafe_allow_html=True)

    for msg in st.session_state.mock_chat_history:
        content = clean_rich(msg["content"])
        content = re.sub(r'^[🎙🎯💡📊📋]\S*\s*[^\n]*?\n', '', content)
        if content:
            bubble_html = chat_bubble(msg["role"], content)
            st.markdown(bubble_html, unsafe_allow_html=True)

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


# ─── Main ────────────────────────────────────────────────

def main():
    init_session()
    render_sidebar()

    page_map = {
        "首页": page_home,
        "素材库": page_material,
        "面试准备": page_prep,
        "模拟面试": page_mock,
    }
    page_fn = page_map.get(st.session_state.page, page_home)
    page_fn()


if __name__ == "__main__":
    main()
