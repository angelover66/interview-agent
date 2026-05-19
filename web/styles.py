"""Minimal CSS for Interview Agent — only essential overrides."""
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
}

/* Hide Streamlit chrome but keep sidebar toggle */
.stApp [data-testid="stToolbar"] { display: none !important; }
.stApp footer { display: none !important; }
.stDeployButton { display: none !important; }
/* NOT hiding #MainMenu — sidebar toggle arrow lives there */

/* ── Typography ── */
h1, h2, h3 { color: var(--text) !important; }

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: var(--bg-sidebar);
    border-right: 1px solid var(--border);
}

/* ── Buttons — only style primary for visibility ── */
.stButton > button[kind="primary"] {
    background: var(--accent) !important;
    border: none !important;
    color: #FFFFFF !important;
}
.stButton > button[kind="primary"]:hover {
    background: #1D4ED8 !important;
}

/* ── Input fields ── */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div {
    border-radius: var(--radius) !important;
    border: 1px solid var(--border) !important;
}

/* ── Tabs ── */
.stTabs [aria-selected="true"] {
    color: var(--accent) !important;
    border-bottom: 2px solid var(--accent) !important;
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
}

.candidate-bubble {
    background: #EFF6FF;
    border-left: 3px solid #2563EB;
    padding: 0.75rem 1rem;
    margin: 0.5rem 0;
}
.candidate-bubble .bubble-speaker {
    font-size: 0.75rem;
    font-weight: 600;
    color: #2563EB;
    margin-bottom: 0.25rem;
}

/* ── Interview status bar ── */
.interview-bar {
    background: var(--bg);
    border: 1px solid var(--border);
    border-left: 3px solid var(--accent);
    padding: 0.6rem 1rem;
    margin-bottom: 1rem;
}
"""
