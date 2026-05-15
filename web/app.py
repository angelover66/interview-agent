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
from core.models import MockSession, MockQuestion, MockAnswer, InterviewRecord
from skills.material import MaterialSkill
from skills.prep import PrepSkill
from skills.mock import MockSkill
from skills.tracker import TrackerSkill

# Import skill modules for console capture
import skills.material as material_module
import skills.prep as prep_module
import skills.mock as mock_module
import skills.tracker as tracker_module

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
        st.session_state.material = MaterialSkill(st.session_state.storage)
        st.session_state.prep = PrepSkill(st.session_state.storage)
        st.session_state.mock = MockSkill(st.session_state.storage)
        st.session_state.tracker = TrackerSkill(st.session_state.storage)

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

    tab1, tab2, tab3 = st.tabs(["导入素材", "素材列表", "候选人画像"])

    # ── Tab 1: 导入 ──
    with tab1:
        st.subheader("导入素材")
        uploaded = st.file_uploader(
            "上传简历 / 项目文档 / JD（支持 .txt / .md / .pdf）",
            type=["txt", "md", "pdf"],
            key="material_uploader",
        )
        if uploaded:
            # Save to temp file
            suffix = Path(uploaded.name).suffix or ".txt"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(uploaded.read())
                tmp_path = tmp.name

            with st.spinner("正在提取结构化信息..."):
                output = capture_output(material_module, st.session_state.material, "import", tmp_path)

            os.unlink(tmp_path)
            display_rich_text(output)
            st.success("素材已入库")

    # ── Tab 2: 列表 ──
    with tab2:
        st.subheader("素材列表")

        # Build list from storage directly
        files = st.session_state.storage.list_raw_files()
        index = st.session_state.storage.get_index()

        col1, col2 = st.columns([3, 1])
        with col1:
            if files:
                for f in files:
                    cat_emoji = {"resumes": "📄", "projects": "📁", "jds": "🎯"}.get(f["category"], "📎")
                    st.markdown(f"{cat_emoji} **{f['name']}** ({f['size']//1024}KB) — *{f['category']}*")
            else:
                st.info("素材库为空，请先导入素材")

        with col2:
            keyword = st.text_input("搜索素材", key="material_search")
            if keyword:
                results = []
                for f in files:
                    try:
                        content = Path(f["path"]).read_text(encoding="utf-8", errors="replace")
                        if keyword.lower() in content.lower():
                            results.append(f)
                    except Exception:
                        continue
                if results:
                    for r in results:
                        st.markdown(f"📎 **{r['name']}**")
                elif keyword:
                    st.caption("无精确匹配")

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

        col1, col2 = st.columns(2)
        with col1:
            company = st.text_input("公司名称", placeholder="如: 字节跳动", key="mock_company")
        with col2:
            position = st.text_input("岗位名称", placeholder="如: 资深B端产品经理", key="mock_position")

        if st.button("🎬 开始面试", type="primary", use_container_width=True, disabled=not (company and position)):
            with st.spinner("面试官正在准备..."):
                mock = st.session_state.mock
                output = capture_output(mock_module, mock, "start", f"{company} {position}")

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


# ─── Page: 面试追踪 ────────────────────────────────────────

def page_tracker():
    st.header("📊 面试追踪")

    tab1, tab2, tab3 = st.tabs(["面试记录", "添加记录", "统计看板"])

    # ── Tab 1: 记录列表 ──
    with tab1:
        records = st.session_state.storage.load_interviews()
        if not records:
            st.info("暂无面试记录，请先添加")
        else:
            # Build a nice table
            rows = []
            for r in records:
                status_emoji = {"待面试": "⏳", "已面试": "✅", "有结果": "📋"}.get(r.get("status", ""), "❓")
                result_emoji = {"通过": "🟢", "offer": "🎉", "挂": "🔴", "待定": "🟡"}.get(r.get("result", ""), "⚪")
                rows.append({
                    "ID": r.get("id", ""),
                    "公司": r.get("company", ""),
                    "岗位": r.get("position", ""),
                    "轮次": r.get("round", ""),
                    "状态": f"{status_emoji} {r.get('status', '')}",
                    "结果": f"{result_emoji} {r.get('result', '')}",
                    "日期": r.get("interview_date", ""),
                })

            st.dataframe(rows, use_container_width=True, hide_index=True)

            # Detail expander
            with st.expander("查看详情 / 更新记录"):
                record_ids = [str(r.get("id")) for r in records]
                selected_id = st.selectbox("选择记录 ID", record_ids)
                if selected_id:
                    target = next((r for r in records if str(r.get("id")) == selected_id), None)
                    if target:
                        st.json(target)

                        st.markdown("---")
                        st.caption("更新记录")
                        new_status = st.selectbox("状态", ["待面试", "已面试", "有结果"],
                                                  index=["待面试", "已面试", "有结果"].index(target.get("status", "待面试")))
                        new_result = st.selectbox("结果", ["", "通过", "挂", "待定", "offer"],
                                                  index=["", "通过", "挂", "待定", "offer"].index(target.get("result", "")))
                        new_exp = st.text_area("面经", value=target.get("experience", ""))
                        new_notes = st.text_input("备注", value=target.get("notes", ""))

                        if st.button("保存更新"):
                            target["status"] = new_status
                            target["result"] = new_result
                            target["experience"] = new_exp
                            target["notes"] = new_notes
                            target["updated_at"] = datetime.now().isoformat()
                            st.session_state.storage.save_interviews(records)
                            st.success("已更新")
                            st.rerun()

    # ── Tab 2: 添加记录 ──
    with tab2:
        st.subheader("添加面试记录")
        with st.form("add_record_form"):
            col_a, col_b = st.columns(2)
            with col_a:
                company = st.text_input("公司", placeholder="如: 字节跳动")
                position = st.text_input("岗位", placeholder="如: 资深B端产品经理")
                interview_date = st.date_input("面试日期")
            with col_b:
                round_name = st.selectbox("轮次", ["一面", "二面", "三面", "HR面", "终面"])
                status = st.selectbox("状态", ["待面试", "已面试", "有结果"])
                result = st.selectbox("结果", ["", "通过", "挂", "待定", "offer"])

            experience = st.text_area("面经记录", placeholder="记录面试问题和心得...")
            notes = st.text_input("备注")

            submitted = st.form_submit_button("保存记录", use_container_width=True)
            if submitted:
                if not company or not position:
                    st.error("公司和岗位为必填项")
                else:
                    records = st.session_state.storage.load_interviews()
                    record = InterviewRecord(
                        company=company,
                        position=position,
                        interview_date=str(interview_date),
                        round=round_name,
                        status=status,
                        result=result,
                        experience=experience,
                        notes=notes,
                        created_at=datetime.now().isoformat(),
                        updated_at=datetime.now().isoformat(),
                    )
                    record_id = len(records) + 1
                    entry = {"id": record_id, **record.to_dict()}
                    records.append(entry)
                    st.session_state.storage.save_interviews(records)
                    st.success(f"记录 #{record_id} 已保存")
                    st.rerun()

    # ── Tab 3: 统计看板 ──
    with tab3:
        records = st.session_state.storage.load_interviews()
        if not records:
            st.info("暂无数据")
            return

        total = len(records)
        pending = sum(1 for r in records if r.get("status") == "待面试")
        interviewed = sum(1 for r in records if r.get("status") in ("已面试", "有结果"))
        passed = sum(1 for r in records if r.get("result") in ("通过", "offer"))
        failed = sum(1 for r in records if r.get("result") == "挂")

        # Metrics row
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("总投递", total)
        c2.metric("待面试", pending)
        c3.metric("已完成", interviewed)
        c4.metric("通过/Offer", passed)
        c5.metric("已挂", failed, delta=None)

        st.markdown("---")

        # Conversion rate
        col_a, col_b = st.columns(2)
        with col_a:
            pass_rate = (passed / (passed + failed) * 100) if (passed + failed) > 0 else 0
            st.metric("通过率", f"{pass_rate:.0f}%")

            # Round distribution
            rounds = {}
            for r in records:
                rnd = r.get("round", "未知")
                rounds[rnd] = rounds.get(rnd, 0) + 1
            st.markdown("**轮次分布**")
            for k, v in sorted(rounds.items()):
                st.markdown(f"- {k}: {v} 次")

        with col_b:
            interview_rate = (interviewed / total * 100) if total > 0 else 0
            st.metric("面试转化率", f"{interview_rate:.0f}%")

            # Company distribution
            companies = {}
            for r in records:
                c = r.get("company", "未知")
                companies[c] = companies.get(c, 0) + 1
            st.markdown("**投递公司**")
            for c_name, count in sorted(companies.items(), key=lambda x: -x[1]):
                st.markdown(f"- {c_name}: {count} 次")

        # Status chart using st.bar_chart
        st.markdown("---")
        st.markdown("**状态分布**")
        status_data = {
            "待面试": pending,
            "已面试": sum(1 for r in records if r.get("status") == "已面试"),
            "有结果": sum(1 for r in records if r.get("status") == "有结果"),
        }
        st.bar_chart(status_data)


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
            "📊 面试追踪": "面试追踪",
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

        # Quick stats
        records = st.session_state.storage.load_interviews()
        pending = sum(1 for r in records if r.get("status") == "待面试")
        st.metric("待面试", pending)

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
        "面试追踪": page_tracker,
    }

    page_fn = page_map.get(st.session_state.page, page_prep)
    page_fn()


if __name__ == "__main__":
    main()
