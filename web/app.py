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
    st.caption("上传 PDF 格式简历。支持多份简历，点击预览可查看文本内容或下载。")

    uploaded = st.file_uploader("上传简历", type=["pdf"], key="resume_uploader_v4", label_visibility="collapsed")
    if uploaded:
        storage = st.session_state.storage
        if storage.resume_exists(uploaded.name):
            storage.delete_resume(uploaded.name)
            path = storage.save_resume(uploaded.name, uploaded.read())
            st.success(f"「{uploaded.name}」已更新")
        else:
            path = storage.save_resume(uploaded.name, uploaded.read())
            st.success(f"「{uploaded.name}」上传成功")
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
                    st.success("简历删除成功")
                    st.rerun()

            if st.session_state.get(f"preview_{pk}", False):
                # Extract text from PDF for inline preview (avoids Chrome iframe block)
                resume_text = _read_file(r['file_path'])
                if resume_text:
                    st.text_area("简历内容预览", value=resume_text[:5000], height=400, key=f"resume_text_{hash(r['file_name'])}", disabled=True)
                else:
                    st.warning("无法提取文本内容，请下载后查看")
                # Download button
                with open(r['file_path'], "rb") as pdf_file:
                    st.download_button(
                        label="📥 下载 PDF",
                        data=pdf_file.read(),
                        file_name=r['file_name'],
                        mime="application/pdf",
                        key=f"resume_dl_{hash(r['file_name'])}",
                    )


# ─── Page 3: 岗位库 ────────────────────────────────────────

def page_position():
    st.header("💼 岗位库")

    # ── 新增岗位按钮 ──
    editing_idx = st.session_state.get("_edit_position_idx")
    if st.button("＋ 新增岗位", type="secondary"):
        st.session_state._show_position_form = True
        st.session_state._edit_position_idx = None
        st.session_state._extracted_position = {}

    # ── 岗位表单弹窗 ──
    if st.session_state.get("_show_position_form", False):
        st.markdown("---")
        is_edit = editing_idx is not None
        st.subheader("编辑岗位" if is_edit else "新增岗位")
        st.caption("上传 JD 图片自动提取四个字段。图片仅用于 AI 识别，不上传存储。")

        if not is_edit:
            jd_file = st.file_uploader("上传 JD 图片", type=["png", "jpg", "jpeg", "webp"], key="jd_file_v5")
            if jd_file:
                # Detect new file upload (compare file name with last processed)
                last_file = st.session_state.get("_last_jd_filename", "")
                if jd_file.name != last_file:
                    st.session_state._extracting = False
                    st.session_state._extracted_position = {}
                    st.session_state._last_jd_filename = jd_file.name

                # Auto-extract (runs once per file)
                if not st.session_state.get("_extracting", False):
                    st.session_state._extracting = True
                    with st.spinner("正在 AI 识别 JD 图片..."):
                        try:
                            api_key = os.environ.get("DASHSCOPE_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
                            if not api_key:
                                st.error("缺少 DASHSCOPE_API_KEY。")
                            else:
                                from openai import OpenAI
                                # Compress on-the-fly for API (quality 30 = ~50KB base64, 不影响文字识别)
                                from PIL import Image as PILImage
                                pil_img = PILImage.open(jd_file)
                                pil_img.thumbnail((600, 600), PILImage.LANCZOS)
                                if pil_img.mode in ('RGBA', 'P'):
                                    pil_img = pil_img.convert('RGB')
                                buf = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
                                pil_img.save(buf.name, 'JPEG', quality=30, optimize=True)
                                compressed_bytes = Path(buf.name).read_bytes()
                                Path(buf.name).unlink()

                                img_b64 = base64.b64encode(compressed_bytes).decode('utf-8')
                                client = OpenAI(api_key=api_key, base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")
                                jd_prompt_text = (Path(__file__).parent.parent / "prompts" / "jd_extract.txt").read_text()
                                resp = client.chat.completions.create(
                                    model="qwen-vl-plus", max_tokens=1024, timeout=30,
                                    messages=[
                                        {"role": "system", "content": jd_prompt_text},
                                        {"role": "user", "content": [
                                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
                                            {"type": "text", "text": "提取结构化岗位信息。只返回 JSON。"}
                                        ]}
                                    ],
                                )
                                raw = resp.choices[0].message.content
                                import re as _re
                                match = _re.search(r'\{[\s\S]*\}', raw)
                                extracted_data = json.loads(match.group()) if match else json.loads(raw)

                                # Write extracted data to session_state keys that widgets read from
                                for field, key in [("company", "pos_company_v6"), ("position", "pos_position_v6"),
                                                    ("responsibilities", "pos_resp_v6"), ("requirements", "pos_req_v6")]:
                                    val = extracted_data.get(field, "")
                                    if isinstance(val, list):
                                        val = "\n".join(val)
                                    st.session_state[key] = val
                                st.session_state._just_extracted = True
                        except Exception as e:
                            st.error(f"识别失败，请手动填写: {e}")
                    st.rerun()

        # Widgets read initial value from session_state (NOT value= parameter)
        # MUST write to session_state BEFORE creating the widget
        if "pos_company_v6" not in st.session_state:
            st.session_state["pos_company_v6"] = ""
        if "pos_position_v6" not in st.session_state:
            st.session_state["pos_position_v6"] = ""
        if "pos_resp_v6" not in st.session_state:
            st.session_state["pos_resp_v6"] = ""
        if "pos_req_v6" not in st.session_state:
            st.session_state["pos_req_v6"] = ""

        if st.session_state.get("_just_extracted", False):
            st.success("识别成功，字段已自动填充。请确认后保存。")
            st.session_state._just_extracted = False

        company = st.text_input("公司名称 *", key="pos_company_v6", placeholder="如：字节跳动")
        position = st.text_input("岗位名称 *", key="pos_position_v6", placeholder="如：资深B端产品经理")
        resp_text = st.text_area("工作职责 *（每行一条）", key="pos_resp_v6", placeholder="负责XX产品的需求分析...")
        req_text = st.text_area("任职要求 *（每行一条）", key="pos_req_v6", placeholder="5年以上B端产品经验...")

        c_save, c_cancel = st.columns([1, 1])
        with c_save:
            label = "💾 保存修改" if is_edit else "💾 保存岗位"
            if st.button(label, type="primary", use_container_width=True, disabled=not (company and position and resp_text.strip() and req_text.strip())):
                data = {
                    "company": company.strip(), "position": position.strip(),
                    "responsibilities": [r.strip() for r in resp_text.strip().split("\n") if r.strip()],
                    "requirements": [r.strip() for r in req_text.strip().split("\n") if r.strip()],
                    "source": "vision" if st.session_state.get("_extracting") else "manual",
                    "created_at": datetime.now().isoformat(),
                }
                if is_edit:
                    st.session_state.storage.update_position(editing_idx, data)
                else:
                    st.session_state.storage.save_position(data)
                # Clean up all form state
                for k in ["_extracted_position", "_show_position_form", "_edit_position_idx",
                           "_just_extracted", "_extracting", "_last_jd_filename",
                           "pos_company_v6", "pos_position_v6", "pos_resp_v6", "pos_req_v6"]:
                    st.session_state.pop(k, None)
                st.success("岗位修改成功" if is_edit else "岗位保存成功")
                st.rerun()
        with c_cancel:
            if st.button("取消", use_container_width=True):
                for k in ["_extracted_position", "_show_position_form", "_edit_position_idx",
                           "_just_extracted", "_extracting", "_last_jd_filename",
                           "pos_company_v6", "pos_position_v6", "pos_resp_v6", "pos_req_v6"]:
                    st.session_state.pop(k, None)
                st.rerun()

    # ── 岗位列表表格 ──
    st.markdown("---")
    positions = st.session_state.storage.list_positions()
    if not positions:
        st.info("岗位库为空，点击上方「＋ 新增岗位」添加")
    else:
        # 表头
        h1, h2, h3, h4, h5, h6 = st.columns([0.5, 2, 2, 3, 3, 1.5])
        with h1:
            st.markdown("**#**")
        with h2:
            st.markdown("**公司名称**")
        with h3:
            st.markdown("**岗位名称**")
        with h4:
            st.markdown("**工作职责**")
        with h5:
            st.markdown("**任职资格**")
        with h6:
            st.markdown("**操作**")
        st.markdown("---")

        for i, p in enumerate(positions):
            resp_summary = "；".join(p.get("responsibilities", []))[:80] + ("..." if len("；".join(p.get("responsibilities", []))) > 80 else "")
            req_summary = "；".join(p.get("requirements", []))[:80] + ("..." if len("；".join(p.get("requirements", []))) > 80 else "")
            c1, c2, c3, c4, c5, c6 = st.columns([0.5, 2, 2, 3, 3, 1.5])
            with c1:
                st.markdown(f"<small>{i+1}</small>", unsafe_allow_html=True)
            with c2:
                st.markdown(f"<small>{p['company']}</small>", unsafe_allow_html=True)
            with c3:
                st.markdown(f"<small>{p['position']}</small>", unsafe_allow_html=True)
            with c4:
                st.markdown(f"<small>{resp_summary}</small>", unsafe_allow_html=True)
            with c5:
                st.markdown(f"<small>{req_summary}</small>", unsafe_allow_html=True)
            with c6:
                ce1, ce2 = st.columns([1, 1])
                with ce1:
                    if st.button("✏️", key=f"pos_edit_{i}"):
                        st.session_state._edit_position_idx = i
                        st.session_state._edit_position_data = dict(p)
                        st.session_state._show_position_form = True
                with ce2:
                    if st.button("🗑", key=f"pos_del_{i}"):
                        st.session_state._confirm_delete_idx = i

    # ── 删除确认 ──
    if st.session_state.get("_confirm_delete_idx") is not None:
        idx = st.session_state["_confirm_delete_idx"]
        p = positions[idx] if idx < len(positions) else None
        if p:
            st.warning(f"确认删除「{p['company']} — {p['position']}」？此操作不可撤销。")
            cc1, cc2 = st.columns([1, 1])
            with cc1:
                if st.button("✅ 确认删除", type="primary"):
                    st.session_state.storage.delete_position(idx)
                    st.session_state._confirm_delete_idx = None
                    st.success("岗位删除成功")
                    st.rerun()
            with cc2:
                if st.button("取消", type="secondary"):
                    st.session_state._confirm_delete_idx = None
                    st.rerun()

    # ── 编辑模式：预填表单 ──
    if st.session_state.get("_edit_position_data"):
        st.session_state._extracted_position = st.session_state._edit_position_data
        st.session_state._show_position_form = True
        st.session_state._edit_position_data = None


# ─── Page 4: 面试准备 ─────────────────────────────────────

def page_prep():
    st.header("📖 面试准备")

    # Step 1: 选简历（仅从简历库选择）
    st.markdown("**📄 选择简历**")
    resumes = st.session_state.storage.list_resumes()
    if resumes:
        resume_names = [r['display_name'] for r in resumes]
        resume_choice = st.selectbox("简历", resume_names, key="prep_resume_choice_v4", label_visibility="collapsed")
        resume_path = next((r['file_path'] for r in resumes if r['display_name'] == resume_choice), "")
    else:
        st.warning("简历库为空，请先去「📄 简历库」上传简历")
        resume_path = ""

    # Step 2: 选岗位（仅从岗位库选择）
    st.markdown("**💼 选择岗位**")
    positions = st.session_state.storage.list_positions()
    if positions:
        position_labels = [f"{p['company']} — {p['position']}" for p in positions]
        position_choice = st.selectbox("岗位", position_labels, key="prep_pos_choice_v4", label_visibility="collapsed")
        position_data = next((p for p in positions if f"{p['company']} — {p['position']}" == position_choice), None)
    else:
        st.warning("岗位库为空，请先去「💼 岗位库」新增岗位")
        position_data = None

    # Step 3: 生成材料（仅需简历+JD，素材库为空也可）
    can_generate = bool(resume_path and position_data)
    if st.button("🚀 生成面试准备材料", type="primary", use_container_width=True, disabled=not can_generate):
        resume_text = _read_file(resume_path)
        jd_text = f"公司: {position_data['company']}\n岗位: {position_data['position']}\n职责: {'; '.join(position_data.get('responsibilities', []))}\n要求: {'; '.join(position_data.get('requirements', []))}"
        file_context = f"简历:\n{resume_text}\n\n岗位信息:\n{jd_text}"

        with st.spinner("生成中..."):
            output = capture_output(prep_module, st.session_state.prep, "for", f"{position_data['company']} {position_data['position']}")
        st.session_state.prep_chat_history.append({"role": "assistant", "content": output or "学习材料已生成"})
        st.session_state.prep._file_context = file_context
        st.rerun()
    if not can_generate:
        st.caption("请先在简历库上传简历、岗位库新增岗位，然后在此选择")

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
            for ph in ["{material_summary}", "{context}", "{search_results}"]:
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
                    # Store evaluation result for display
                    st.session_state._eval_result = review_out
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

            # Show last evaluation if available
            if st.session_state.get("_eval_result"):
                st.markdown("---")
                st.subheader("📊 最近评估报告")
                display_rich(st.session_state._eval_result)

        # ── History (always visible after any completed interview) ──
        st.markdown("---")
        st.subheader("📋 历史面试记录")
        sessions = st.session_state.storage.list_sessions()
        if sessions:
            for s in sessions:
                score = s.get("overall_score", 0)
                score_str = f"⭐ {score}/10" if score else "未评分"
                dim_scores = s.get("dimension_scores", {})
                dim_str = " | ".join(f"{k}: {v}" for k, v in dim_scores.items()) if dim_scores else ""
                answers = s.get("answers", [])
                questions = s.get("questions", [])
                with st.expander(f"{s.get('company', '?')} — {s.get('position', '?')} | {score_str} | {(s.get('started_at','') or '')[:10]}"):
                    st.markdown(f"**总分**: {score_str}")
                    if dim_str:
                        st.markdown(f"**维度评分**: {dim_str}")
                    if s.get("summary"):
                        st.markdown(f"**总结**: {s['summary']}")
                    if s.get("strengths"):
                        st.markdown("**优势**: " + "、".join(s["strengths"]))
                    if s.get("weaknesses"):
                        st.markdown("**不足**: " + "、".join(s["weaknesses"]))
                    if s.get("sample_answer"):
                        with st.expander("📝 示范回答"):
                            st.markdown(s["sample_answer"])
                    if s.get("priority_improvements"):
                        with st.expander("🔧 改进建议"):
                            for pi in s["priority_improvements"]:
                                st.markdown(f"- [{pi.get('priority', '')}] **{pi.get('area', '')}**: {pi.get('suggestion', '')}")
                    # Full Q&A transcript
                    if questions or answers:
                        with st.expander("💬 完整面试对话"):
                            for i, (q, a) in enumerate(zip(questions, answers)):
                                st.markdown(f"**Q{i+1}**: {q.get('question', '?')[:200]}")
                                st.markdown(f"**A{i+1}**: {a.get('answer', '?')[:500]}")
                                if a.get("score"):
                                    st.caption(f"评分: {a['score']}/10")
                                st.markdown("---")
                    st.caption(f"时间: {s.get('started_at', '')[:16]} | 题数: {len(answers)}")
        else:
            st.caption("暂无历史记录")
        return

    # ── Setup ──
    if not st.session_state.mock_started:
        st.caption("选择简历和岗位，AI 面试官将进行模拟面试（共 10 题）")

        # Resume (from library only)
        st.markdown("**📄 选择简历**")
        resumes = st.session_state.storage.list_resumes()
        if resumes:
            resume_names = [r['display_name'] for r in resumes]
            resume_choice = st.selectbox("简历", resume_names, key="mock_resume_choice_v4", label_visibility="collapsed")
            resume_path = next((r['file_path'] for r in resumes if r['display_name'] == resume_choice), "")
        else:
            st.warning("简历库为空，请先去「📄 简历库」上传简历")
            resume_path = ""

        # Position (from library only)
        st.markdown("**💼 选择岗位**")
        positions = st.session_state.storage.list_positions()
        if positions:
            position_labels = [f"{p['company']} — {p['position']}" for p in positions]
            position_choice = st.selectbox("岗位", position_labels, key="mock_pos_choice_v4", label_visibility="collapsed")
            position_data = next((p for p in positions if f"{p['company']} — {p['position']}" == position_choice), None)
        else:
            st.warning("岗位库为空，请先去「💼 岗位库」新增岗位")
            position_data = None

        can_start = bool(resume_path and position_data)
        if st.button("🎬 开始面试", type="primary", use_container_width=True, disabled=not can_start):
            mock = st.session_state.mock
            mock._selected_resume_path = resume_path
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
        if not can_start:
            st.caption("请先在简历库上传简历、岗位库新增岗位，然后在此选择")
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

    # Voice input (requires streamlit-mic-recorder + OPENAI_API_KEY)
    # TODO: enable when Streamlit Cloud supports native mic access
    # from streamlit_mic_recorder import mic_recorder
    # audio = mic_recorder(start_prompt="🎤 录音", stop_prompt="⏹ 停止", key="mock_voice_v3")

    answer = st.chat_input("输入你的回答...", key="mock_answer_v4")

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
