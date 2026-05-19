"""Minimal CSS theme for Interview Agent — clean, accessible, no decoration."""
from __future__ import annotations

THEME_CSS = """
/* ── Variables ── */
:root {
    --accent: #2563EB;
    --accent-light: #EFF6FF;
    --text: #111827;
    --text-secondary: #6B7280;
    --bg: #FFFFFF;
    --bg-sidebar: #F8FAFC;
    --border: #E5E7EB;
    --radius: 6px;
}

/* ── Global ── */
.stApp {
    background: var(--bg);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
}

/* Hide Streamlit junk — use visibility (not display:none) to keep sidebar toggle clickable */
.stApp [data-testid="stToolbar"] { display: none !important; }
.stApp footer { display: none !important; }
#MainMenu { visibility: hidden; }
.stDeployButton { display: none !important; }

/* ── Typography ── */
h1, h2, h3, h4 { color: var(--text) !important; }
h1 { font-size: 1.5rem !important; font-weight: 700 !important; }
h2 { font-size: 1.25rem !important; font-weight: 600 !important; }
h3 { font-size: 1.1rem !important; font-weight: 600 !important; }

p, span, label { color: var(--text); }

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: var(--bg-sidebar);
    border-right: 1px solid var(--border);
}
[data-testid="stSidebar"] [data-testid="stMarkdown"] p,
[data-testid="stSidebar"] [data-testid="stMarkdown"] span {
    font-size: 0.9rem;
}
[data-testid="stSidebar"] .stRadio label {
    padding: 0.5rem 0.75rem !important;
    border-radius: var(--radius) !important;
    margin-bottom: 2px !important;
    font-size: 0.9rem !important;
    color: var(--text) !important;
    transition: background 0.1s ease;
}
[data-testid="stSidebar"] .stRadio label:hover {
    background: #EEF2FF;
}
/* The checked radio label — Streamlit applies aria-checked */
[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked) {
    background: var(--accent-light) !important;
    color: var(--accent) !important;
    font-weight: 600 !important;
}

/* ── Buttons ── */
.stButton > button {
    font-weight: 500 !important;
    border-radius: var(--radius) !important;
    transition: all 0.15s ease !important;
    background: #F3F4F6 !important;
    border: 1px solid #D1D5DB !important;
    color: #374151 !important;
}
.stButton > button:hover {
    background: #E5E7EB !important;
    border-color: #9CA3AF !important;
}
.stButton > button[kind="primary"] {
    background: var(--accent) !important;
    border: none !important;
    color: #FFFFFF !important;
}
.stButton > button[kind="primary"]:hover {
    background: #1D4ED8 !important;
}
.stButton > button[kind="secondary"] {
    background: #F9FAFB !important;
    border: 1px solid #D1D5DB !important;
    color: #374151 !important;
}
.stButton > button[kind="secondary"]:hover {
    background: #F3F4F6 !important;
    border-color: var(--accent) !important;
    color: var(--accent) !important;
}

/* ── Input fields ── */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div {
    border-radius: var(--radius) !important;
    border: 1px solid var(--border) !important;
    background: var(--bg) !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px rgba(37,99,235,0.1) !important;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    border-bottom: 1px solid var(--border) !important;
    gap: 0 !important;
}
.stTabs [data-baseweb="tab"] {
    font-weight: 500 !important;
    padding: 0.5rem 1rem !important;
    border-radius: 0 !important;
    color: var(--text-secondary) !important;
}
.stTabs [aria-selected="true"] {
    color: var(--accent) !important;
    border-bottom: 2px solid var(--accent) !important;
}

/* ── File uploader ── */
[data-testid="stFileUploader"] {
    border-radius: var(--radius) !important;
    border: 2px dashed var(--border) !important;
    background: #FAFBFC !important;
}
[data-testid="stFileUploader"]:hover {
    border-color: var(--accent) !important;
}

/* ── Expander ── */
[data-testid="stExpander"] {
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
}

/* ── Chat bubbles ── */
.interviewer-bubble {
    background: #FEF2F2;
    border-left: 3px solid #EF4444;
    padding: 0.75rem 1rem;
    margin: 0.5rem 0;
}
.interviewer-bubble .bubble-speaker {
    font-size: 0.75rem;
    font-weight: 600;
    color: #DC2626;
    margin-bottom: 0.25rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.candidate-bubble {
    background: #EFF6FF;
    border-left: 3px solid var(--accent);
    padding: 0.75rem 1rem;
    margin: 0.5rem 0;
}
.candidate-bubble .bubble-speaker {
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--accent);
    margin-bottom: 0.25rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

/* ── Interview status bar ── */
.interview-bar {
    background: var(--bg);
    border: 1px solid var(--border);
    border-left: 3px solid var(--accent);
    padding: 0.6rem 1rem;
    margin-bottom: 1rem;
}

/* ── Alerts ── */
.stAlert {
    border-radius: var(--radius) !important;
    border: none !important;
}

/* ── Chat input ── */
[data-testid="stChatInput"] textarea {
    border-radius: var(--radius) !important;
    border: 1px solid var(--border) !important;
    background: var(--bg) !important;
}

/* ── Radio buttons ── */
.stRadio label {
    color: var(--text) !important;
}

/* ── Section divider ── */
.section-divider {
    border-top: 1px solid var(--border);
    margin: 1rem 0;
}
"""
