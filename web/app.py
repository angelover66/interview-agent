"""Streamlit Web UI — v2.0 五模块结构."""
from __future__ import annotations
import sys, re, os, json, tempfile, base64
from pathlib import Path
from io import StringIO
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

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

import skills.material as material_module
import skills.prep as prep_module
import skills.mock as mock_module

from web.ui import rich_to_html
from web.styles import THEME_CSS

# ─── Page config ─────────────────────────────────────────

st.set_page_config(page_title="面试助手", page_icon="🎯", layout="wide")
st.markdown(f"<style>{THEME_CSS}</style>", unsafe_allow_html=True)

# ─── Session state ───────────────────────────────────────

def init_session():
    if "storage" not in st.session_state:
        st.session_state.storage = StorageManager(base_dir="./data")
        st.session_state.material = MaterialSkill(st.session_state.storage, None)
        st.session_state.prep = PrepSkill(st.session_state.storage, None)
        st.session_state.mock = MockSkill(st.session_state.storage)

        st.session_state.mock_active = False
        st.session_state.mock_chat_history = []
        st.session_state.mock_started = False
        st.session_state.show_review = False

        st.session_state.prep_chat_history = []
        st.session_state.prep_target = ""

        st.session_state.page = "素材库"


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
    return rich_to_html(re.sub(r'[╭╮╰╯│├└┬┴┼═─━]', '', text).strip())


def display_rich(text: str):
    cleaned = clean_rich(text)
    if cleaned:
        st.markdown(cleaned, unsafe_allow_html=True)


def chat_bubble(role: str, content: str) -> str:
    if role == "assistant":
        return f"""<div class="interviewer-bubble"><div class="bubble-speaker">面试官</div>{content}</div>"""
    else:
        return f"""<div class="candidate-bubble"><div class="bubble-speaker">候选人</div>{content}</div>"""


def _read_file(path: str) -> str:
    if not path or not Path(path).exists():
        return ""
    fp = Path(path)
    s = fp.suffix.lower()
    try:
        if s == '.pdf':
            from pdfminer.high_level import extract_text
            return extract_text(str(fp))[:5000]
        elif s in ('.xlsx', '.xls'):
            import openpyxl
            wb = openpyxl.load_workbook(str(fp), data_only=True)
            text = ""
            for ws in wb.worksheets:
                for row in ws.iter_rows(values_only=True):
                    text += " ".join(str(c) for c in row if c) + "\n"
            return text[:5000]
        else:
            return fp.read_text(encoding='utf-8', errors='replace')[:5000]
    except Exception:
        return ""


# ─── Sidebar ──────────────────────────────────────────────

def render_sidebar():
    with st.sidebar:
        st.markdown("## 🎯 面试助手")

        pages = ["📚  素材库", "📄  简历库", "💼  岗位库", "📖  面试准备", "🎯  模拟面试"]
        page_map = {p: p.split("  ")[1] for p in pages}

        current_label = next((k for k, v in page_map.items() if v == st.session_state.page), pages[0])
        idx = pages.index(current_label) if current_label in pages else 0

        selected = st.radio("导航", pages, index=idx, key="sidebar_nav_v3")
        page = page_map[selected]
        if page != st.session_state.page:
            st.session_state.page = page
            st.rerun()


# ─── Page 1: 素材库 ─────────────────────────────────────────

def page_material():
    st.header("📚 素材库")
    st.caption("知识库：上传参考资料、笔记、项目文档。简历和 JD 请分别上传到简历库和岗位库。")

    uploaded = st.file_uploader(
        "上传素材", type=["txt", "md", "pdf", "xlsx", "xls", "png", "jpg", "jpeg", "webp"],
        key="material_uploader_v3", label_visibility="collapsed",
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

    st.markdown("---")

    files = st.session_state.storage.list_raw_files()
    if not files:
        st.info("素材库为空，上传参考资料开始构建知识库")
    else:
        keyword = st.text_input("搜索", placeholder="输入关键词...", key="material_search_v3", label_visibility="collapsed")
        display_files = files
        if keyword:
            display_files = [f for f in files if keyword.lower() in Path(f["path"]).read_text(encoding="utf-8", errors="replace").lower()]
            if not display_files:
                st.caption("无匹配结果")

        for f in display_files:
            cat_emoji = {"resumes": "📄", "projects": "📁", "jds": "🎯", "images": "🖼️"}.get(f.get("category", ""), "📎")
            is_img = f.get("category") == "images" or f.get("name", "").lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif"))
            size_kb = f.get("size", 0) // 1024

            c1, c2, c3 = st.columns([5, 1, 1])
            with c1:
                st.markdown(f"{cat_emoji} **{f['name']}**  `{size_kb}KB`")
            with c2:
                vk = f"mat_view_{hash(f['path'])}"
                if st.button("🖼️" if is_img else "📖", key=vk):
                    sk = f"mat_show_{hash(f['path'])}"
                    st.session_state[sk] = not st.session_state.get(sk, False)
            with c3:
                if st.button("🗑", key=f"mat_del_{hash(f['name'] + f.get('category', ''))}"):
                    st.session_state.material.run("delete", f["name"])
                    st.rerun()

            sk = f"mat_show_{hash(f['path'])}"
            if st.session_state.get(sk, False):
                if is_img:
                    try:
                        st.image(f["path"], caption=f["name"], use_container_width=True)
                    except Exception:
                        st.error("无法加载图片")
                else:
                    try:
                        st.text(Path(f["path"]).read_text(encoding="utf-8", errors="replace")[:3000])
                    except Exception:
                        st.error("无法读取文件")


# ─── Page 2: 简历库 ────────────────────────────────────────

def page_resume():
    st.header("📄 简历库")
    st.caption("上传 PDF 格式简历。支持多份简历，点击预览。")

    uploaded = st.file_uploader("上传简历", type=["pdf"], key="resume_uploader_v3", label_visibility="collapsed")
    if uploaded:
        storage = st.session_state.storage
        if storage.resume_exists(uploaded.name):
            st.warning(f"「{uploaded.name}」已存在")
        else:
            path = storage.save_resume(uploaded.name, uploaded.read())
            st.success(f"「{uploaded.name}」已保存")
            st.rerun()

    st.markdown("---")

    resumes = st.session_state.storage.list_resumes()
    if not resumes:
        st.info("简历库为空，请上传 PDF 简历")
    else:
        for i, r in enumerate(resumes):
            c1, c2, c3 = st.columns([5, 1, 1])
            with c1:
                st.markdown(f"📄 **{r['display_name']}**  `{r['file_name']}`")
                st.caption(f"上传时间：{r['uploaded_at'][:16]}")
            with c2:
                pk = f"resume_preview_{r['file_name']}"
                if st.button("🔍 预览", key=pk):
                    st.session_state[f"preview_{pk}"] = not st.session_state.get(f"preview_{pk}", False)
            with c3:
                if st.button("🗑", key=f"resume_del_{r['file_name']}"):
                    st.session_state.storage.delete_resume(r['file_name'])
                    st.rerun()

            if st.session_state.get(f"preview_{pk}", False):
                with open(r['file_path'], "rb") as pdf_file:
                    base64_pdf = base64.b64encode(pdf_file.read()).decode('utf-8')
                    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600" style="border:1px solid #e5e7eb;border-radius:6px;"></iframe>'
                    st.markdown(pdf_display, unsafe_allow_html=True)


# ─── Page 3: 岗位库 ────────────────────────────────────────

def page_position():
    st.header("💼 岗位库")
    st.caption("管理目标岗位信息。支持上传 JD 图片自动提取，或手动填写。")

    tab1, tab2 = st.tabs(["📋 岗位列表", "➕ 新增岗位"])

    with tab2:
        st.subheader("新增岗位")
        mode = st.radio("录入方式", ["📷 上传 JD 图片自动提取", "✏️ 手动填写"], horizontal=True, key="position_mode_v3", label_visibility="collapsed")

        if "上传" in mode:
            jd_image = st.file_uploader("上传 JD 截图/照片", type=["png", "jpg", "jpeg", "webp"], key="jd_image_v3")
            if jd_image:
                st.image(jd_image, caption="JD 预览", width=400)
                if st.button("🔍 自动提取", type="primary"):
                    with st.spinner("正在分析 JD 图片..."):
                        try:
                            import anthropic
                            client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
                            img_data = base64.b64encode(jd_image.read()).decode('utf-8')
                            media_type = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}.get(jd_image.name.split('.')[-1].lower(), "image/png")

                            jd_prompt = Path(__file__).parent.parent / "prompts" / "jd_extract.txt"
                            jd_prompt_text = jd_prompt.read_text() if jd_prompt.exists() else "提取JD结构化信息"

                            resp = client.messages.create(
                                model="claude-sonnet-4-6",
                                max_tokens=1024,
                                system=jd_prompt_text,
                                messages=[{"role": "user", "content": [
                                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": img_data}},
                                    {"type": "text", "text": "请从这张图片中提取结构化岗位信息。"}
                                ]}],
                            )
                            result = json.loads(resp.content[0].text.split("{",1)[1].rsplit("}",1)[0])
                            result = "{" + result + "}"
                            extracted = json.loads(result)
                            st.session_state._extracted_position = extracted
                            st.success("提取成功！请确认下方信息后保存。")
                        except Exception as e:
                            st.error(f"提取失败: {e}")
                            st.session_state._extracted_position = None

        # Form fields
        extracted = st.session_state.get("_extracted_position", {}) or {}
        company = st.text_input("公司名称 *", value=extracted.get("company", ""), key="pos_company_v3", placeholder="如：字节跳动")
        position = st.text_input("岗位名称 *", value=extracted.get("position", ""), key="pos_position_v3", placeholder="如：资深B端产品经理")
        resp_text = st.text_area("工作职责 *（每行一条）", value="\n".join(extracted.get("responsibilities", [])), key="pos_resp_v3", placeholder="负责飞书产品的需求分析...\n制定产品路线图...")
        req_text = st.text_area("任职要求 *（每行一条）", value="\n".join(extracted.get("requirements", [])), key="pos_req_v3", placeholder="5年以上B端产品经验...\n熟悉SaaS产品设计...")

        if st.button("💾 保存岗位", type="primary", disabled=not (company and position and resp_text.strip() and req_text.strip())):
            data = {
                "company": company.strip(),
                "position": position.strip(),
                "responsibilities": [r.strip() for r in resp_text.strip().split("\n") if r.strip()],
                "requirements": [r.strip() for r in req_text.strip().split("\n") if r.strip()],
                "source": "vision" if "上传" in mode and st.session_state.get("_extracted_position") else "manual",
                "created_at": datetime.now().isoformat(),
            }
            st.session_state.storage.save_position(data)
            st.session_state._extracted_position = None
            st.success("岗位已保存")
            st.rerun()

    with tab1:
        positions = st.session_state.storage.list_positions()
        if not positions:
            st.info("岗位库为空，请先新增岗位")
        else:
            for i, p in enumerate(positions):
                with st.expander(f"{p['company']} — {p['position']}"):
                    st.markdown(f"**公司**：{p['company']}")
                    st.markdown(f"**岗位**：{p['position']}")
                    st.markdown("**工作职责**：")
                    for r in p.get("responsibilities", []):
                        st.markdown(f"- {r}")
                    st.markdown("**任职要求**：")
                    for r in p.get("requirements", []):
                        st.markdown(f"- {r}")
                    st.caption(f"来源：{p.get('source', 'manual')} | 创建：{p.get('created_at', '')[:16]}")
                    if st.button("🗑 删除", key=f"pos_del_{i}"):
                        st.session_state.storage.delete_position(i)
                        st.rerun()


# ─── Page 4: 面试准备 ─────────────────────────────────────

def page_prep():
    st.header("📖 面试准备")

    # Step 1: 选简历
    st.markdown("**📄 选择简历**")
    resumes = st.session_state.storage.list_resumes()
    resume_names = [r['display_name'] for r in resumes] if resumes else []
    resume_names.append("➕ 上传新简历")
    resume_choice = st.selectbox("简历", resume_names, key="prep_resume_choice_v3", label_visibility="collapsed")

    resume_path = ""
    if resume_choice == "➕ 上传新简历":
        new_resume = st.file_uploader("上传 PDF 简历", type=["pdf"], key="prep_new_resume_v3")
        if new_resume:
            path = st.session_state.storage.save_resume(new_resume.name, new_resume.read())
            resume_path = path
            st.success(f"已保存并同步到简历库")
    else:
        for r in resumes:
            if r['display_name'] == resume_choice:
                resume_path = r['file_path']
                break

    # Step 2: 选岗位
    st.markdown("**💼 选择岗位**")
    positions = st.session_state.storage.list_positions()
    position_labels = [f"{p['company']} — {p['position']}" for p in positions] if positions else []
    position_labels.append("➕ 新增岗位")
    position_choice = st.selectbox("岗位", position_labels, key="prep_pos_choice_v3", label_visibility="collapsed")

    position_data = None
    if position_choice == "➕ 新增岗位":
        with st.expander("手动填写岗位信息"):
            company = st.text_input("公司名称 *", key="prep_new_company_v3")
            pos_name = st.text_input("岗位名称 *", key="prep_new_pos_v3")
            resp_text = st.text_area("工作职责 *", key="prep_new_resp_v3", placeholder="每行一条")
            req_text = st.text_area("任职要求 *", key="prep_new_req_v3", placeholder="每行一条")
            if st.button("💾 保存并选择", disabled=not (company and pos_name and resp_text.strip() and req_text.strip())):
                position_data = {
                    "company": company.strip(), "position": pos_name.strip(),
                    "responsibilities": [r.strip() for r in resp_text.strip().split("\n") if r.strip()],
                    "requirements": [r.strip() for r in req_text.strip().split("\n") if r.strip()],
                    "source": "manual", "created_at": datetime.now().isoformat(),
                }
                st.session_state.storage.save_position(position_data)
                st.rerun()
    else:
        for p in positions:
            if f"{p['company']} — {p['position']}" == position_choice:
                position_data = p
                break

    # Step 3: 生成材料
    can_generate = bool(resume_path and position_data)
    if can_generate:
        if st.button("🚀 生成面试准备材料", type="primary", use_container_width=True):
            resume_text = _read_file(resume_path)
            jd_text = f"公司: {position_data['company']}\n岗位: {position_data['position']}\n职责: {'; '.join(position_data.get('responsibilities', []))}\n要求: {'; '.join(position_data.get('requirements', []))}"
            file_context = f"简历:\n{resume_text}\n\n岗位信息:\n{jd_text}"

            with st.spinner("生成中..."):
                output = capture_output(prep_module, st.session_state.prep, "for", f"{position_data['company']} {position_data['position']}")
            st.session_state.prep_chat_history.append({"role": "assistant", "content": output or "学习材料已生成"})
            st.session_state.prep._file_context = file_context
            st.rerun()

    # Chat
    if st.session_state.prep_chat_history:
        st.markdown("---")
        for msg in st.session_state.prep_chat_history:
            content = clean_rich(msg["content"])
            st.markdown(chat_bubble(msg["role"], content), unsafe_allow_html=True)
        if st.button("清空对话", type="secondary"):
            st.session_state.prep_chat_history = []
            st.session_state.prep._conversation_history = []
            st.rerun()

    question = st.chat_input("输入问题...", key="prep_chat_v3")
    if question:
        st.session_state.prep_chat_history.append({"role": "user", "content": question})
        with st.spinner("思考中..."):
            prep = st.session_state.prep
            fc = getattr(prep, '_file_context', '')
            sp = Path(__file__).parent.parent / "prompts" / "prep_assistant.txt"
            system = sp.read_text() if sp.exists() else "你是面试准备助手"
            for ph in ["{profile_summary}", "{material_summary}", "{context}", "{search_results}"]:
                system = system.replace(ph, fc[:5000])
            prep._conversation_history.append({"role": "user", "content": question})
            try:
                resp = chat(system=system, messages=prep._conversation_history[-10:], temperature=0.5)
            except Exception as e:
                resp = f"回答失败: {e}"
            prep._conversation_history.append({"role": "assistant", "content": resp})
        st.session_state.prep_chat_history.append({"role": "assistant", "content": resp})
        st.rerun()


# ─── Page 5: 模拟面试 ─────────────────────────────────────

def page_mock():
    st.header("🎯 模拟面试")

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
                    for k in ["mock", "mock_started", "mock_active", "mock_chat_history", "show_review"]:
                        st.session_state.pop(k, None)
                    st.session_state.mock = MockSkill(st.session_state.storage)
                    st.session_state.mock_started = False
                    st.session_state.mock_active = False
                    st.session_state.mock_chat_history = []
                    st.session_state.show_review = False
                    st.rerun()

            # History
            st.markdown("---")
            st.subheader("📋 历史面试记录")
            sessions = st.session_state.storage.list_sessions()
            if sessions:
                for s in sessions:
                    score = s.get("overall_score", 0)
                    score_str = f"⭐ {score}/10" if score else "未评分"
                    dim_scores = s.get("dimension_scores", {})
                    dim_str = " | ".join(f"{k}: {v}" for k, v in dim_scores.items()) if dim_scores else ""
                    with st.expander(f"{s.get('company', '?')} — {s.get('position', '?')} | {score_str} | {(s.get('started_at','') or '')[:10]}"):
                        st.markdown(f"**总分**: {score_str}")
                        if dim_str:
                            st.markdown(f"**维度评分**: {dim_str}")
                        if s.get("summary"):
                            st.markdown(f"**总结**: {s['summary']}")
                        st.caption(f"时间: {s.get('started_at', '')[:16]} | 题数: {len(s.get('answers', []))}")
            else:
                st.caption("暂无历史记录")
            return

    # ── Setup ──
    if not st.session_state.mock_started:
        st.caption("选择简历和岗位，AI 面试官将进行模拟面试（共 10 题）")

        # Resume selection
        st.markdown("**📄 选择简历**")
        resumes = st.session_state.storage.list_resumes()
        resume_names = [r['display_name'] for r in resumes] if resumes else []
        resume_names.append("➕ 上传新简历")
        resume_choice = st.selectbox("简历", resume_names, key="mock_resume_choice_v3", label_visibility="collapsed")
        resume_path = ""
        if resume_choice == "➕ 上传新简历":
            new_resume = st.file_uploader("上传 PDF 简历", type=["pdf"], key="mock_new_resume_v3")
            if new_resume:
                resume_path = st.session_state.storage.save_resume(new_resume.name, new_resume.read())
                st.success("已保存并同步到简历库")
        else:
            for r in resumes:
                if r['display_name'] == resume_choice:
                    resume_path = r['file_path']
                    break

        # Position selection
        st.markdown("**💼 选择岗位**")
        positions = st.session_state.storage.list_positions()
        position_labels = [f"{p['company']} — {p['position']}" for p in positions] if positions else []
        position_labels.append("➕ 新增岗位")
        position_choice = st.selectbox("岗位", position_labels, key="mock_pos_choice_v3", label_visibility="collapsed")
        position_data = None
        if position_choice == "➕ 新增岗位":
            with st.expander("手动填写岗位信息"):
                company = st.text_input("公司名称 *", key="mock_new_company_v3")
                pos_name = st.text_input("岗位名称 *", key="mock_new_pos_v3")
                resp_text = st.text_area("工作职责 *", key="mock_new_resp_v3", placeholder="每行一条")
                req_text = st.text_area("任职要求 *", key="mock_new_req_v3", placeholder="每行一条")
                if st.button("💾 保存并选择", disabled=not (company and pos_name and resp_text.strip() and req_text.strip())):
                    position_data = {
                        "company": company.strip(), "position": pos_name.strip(),
                        "responsibilities": [r.strip() for r in resp_text.strip().split("\n") if r.strip()],
                        "requirements": [r.strip() for r in req_text.strip().split("\n") if r.strip()],
                        "source": "manual", "created_at": datetime.now().isoformat(),
                    }
                    st.session_state.storage.save_position(position_data)
                    st.rerun()
        else:
            for p in positions:
                if f"{p['company']} — {p['position']}" == position_choice:
                    position_data = p
                    break

        can_start = bool(resume_path and position_data)
        if st.button("🎬 开始面试", type="primary", use_container_width=True, disabled=not can_start):
            mock = st.session_state.mock
            mock._selected_resume_path = resume_path
            jd_path = ""
            if position_data:
                jd_text = f"公司: {position_data['company']}\n岗位: {position_data['position']}\n职责: {'; '.join(position_data.get('responsibilities', []))}\n要求: {'; '.join(position_data.get('requirements', []))}"
                jd_dir = Path(tempfile.gettempdir()) / "interview_agent_uploads"
                jd_dir.mkdir(exist_ok=True)
                jd_path = str(jd_dir / f"jd_{hash(jd_text)}.txt")
                Path(jd_path).write_text(jd_text)
                mock._selected_jd_path = jd_path

            with st.spinner("面试官准备中..."):
                output = capture_output(mock_module, mock, "start", f"{position_data['company']} {position_data['position']}")
            cleaned = clean_rich(output)
            st.session_state.mock_chat_history = [{"role": "assistant", "content": cleaned or output}]
            st.session_state._mock_position = position_data
            st.session_state.mock_started = True
            st.session_state.mock_active = True
            st.rerun()
        return

    # ── Active interview ──
    mock = st.session_state.mock
    pos_data = st.session_state.get("_mock_position")

    if pos_data:
        st.markdown(f"""
        <div class="interview-bar">
            🏢 <strong>{pos_data['company']}</strong> — {pos_data['position']} &nbsp;|&nbsp;
            已答 <strong>{len(mock.current_session.answers) if mock.current_session else 0}</strong> 题
        </div>
        """, unsafe_allow_html=True)

    for msg in st.session_state.mock_chat_history:
        content = clean_rich(msg["content"])
        content = re.sub(r'^[🎙🎯💡📊📋]\S*\s*[^\n]*?\n', '', content)
        if content:
            st.markdown(chat_bubble(msg["role"], content), unsafe_allow_html=True)

    # Voice input
    c_voice, c_text = st.columns([1, 4])
    with c_voice:
        try:
            from streamlit_mic_recorder import mic_recorder
            audio = mic_recorder(start_prompt="🎤 录音", stop_prompt="⏹ 停止", key="mock_voice_v3")
            if audio and audio.get("bytes"):
                with st.spinner("语音转文字中..."):
                    import openai
                    client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
                    audio_file = StringIO()
                    audio_file.write(audio["bytes"])
                    audio_file.name = "audio.webm"
                    transcript = client.audio.transcriptions.create(model="whisper-1", file=audio_file)
                    if transcript.text:
                        st.session_state._voice_text = transcript.text
        except ImportError:
            st.caption("语音功能未安装")

    voice_text = st.session_state.get("_voice_text", "")
    answer = st.chat_input("输入你的回答..." if not voice_text else f"🎤: {voice_text[:50]}...", key="mock_answer_v3")
    final_answer = voice_text or answer

    if final_answer:
        st.session_state._voice_text = ""
        st.session_state.mock_chat_history.append({"role": "user", "content": final_answer})
        with st.spinner("面试官思考中..."):
            interviewer_resp = capture_output(mock_module, mock, "answer", final_answer)
        cleaned = clean_rich(interviewer_resp)
        st.session_state.mock_chat_history.append({"role": "assistant", "content": cleaned or interviewer_resp})

        if mock.current_session and len(mock.current_session.answers) >= 10:
            st.session_state.mock_started = False
            st.session_state.mock_active = False
            st.session_state.show_review = True
            st.warning("已达最大题数 (10题)，面试自动结束。")
        st.rerun()

    # End button
    if st.button("⏹ 结束面试", type="secondary"):
        mock.run("end", "")
        st.session_state.mock_started = False
        st.session_state.mock_active = False
        st.session_state.show_review = True
        st.rerun()


# ─── Main ────────────────────────────────────────────────

def main():
    init_session()
    render_sidebar()

    page_map = {
        "素材库": page_material,
        "简历库": page_resume,
        "岗位库": page_position,
        "面试准备": page_prep,
        "模拟面试": page_mock,
    }
    page_fn = page_map.get(st.session_state.page, page_material)
    page_fn()


if __name__ == "__main__":
    main()
