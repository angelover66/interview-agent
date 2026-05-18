"""CSS theme for Interview Agent — Japanese Editorial style.

Design language: warm paper tones, DM Serif Display headings, vermillion accents,
generous negative space, asymmetrical card layouts.
"""
from __future__ import annotations

THEME_CSS = r"""
/* ── Fonts ── */
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600;9..40,700&display=swap');

/* ── Streamlit root variable overrides ── */
.stApp {
    --primary-color: #2D2B55;
    --background-color: #FAF8F5;
    --secondary-background-color: #FFFFFF;
    --text-color: #1E1D1C;
    --font: 'DM Sans', -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
    background: #FAF8F5;
    font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
}

/* ── CSS Design Tokens ── */
:root {
    --ink: #1E1D1C;
    --ink-light: #6B6560;
    --ink-muted: #9E988F;
    --paper: #FAF8F5;
    --surface: #FFFFFF;
    --indigo: #2D2B55;
    --indigo-light: #EEEDF5;
    --vermillion: #C44536;
    --vermillion-light: #FDF0ED;
    --sage: #6B8F71;
    --sage-light: #EDF4EE;
    --amber: #B8863A;
    --amber-light: #FDF6ED;
    --border: #E8E5E0;
    --border-strong: #D4D0C8;
    --radius: 4px;
    --radius-lg: 8px;
    --shadow-card: 0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.03);
    --shadow-elevated: 0 4px 12px rgba(0,0,0,0.06), 0 1px 3px rgba(0,0,0,0.04);
    --font-display: 'DM Serif Display', 'Noto Serif SC', 'Songti SC', 'SimSun', serif;
    --font-sans: 'DM Sans', -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
}

/* ── Hide Streamlit chrome ── */
.stApp header[data-testid="stHeader"] {
    background: transparent !important;
    height: 0 !important;
    min-height: 0 !important;
}
.stApp [data-testid="stToolbar"] { display: none !important; }
.stApp footer { display: none !important; }
#MainMenu { display: none !important; }
.stDeployButton { display: none !important; }
/* Reduce top padding of main block */
.stApp .block-container {
    padding-top: 1rem !important;
}

/* ── Typography ── */
h1, h2, h3, h4 {
    font-family: var(--font-display) !important;
    color: var(--ink) !important;
    letter-spacing: -0.01em;
}
h1 { font-size: 2.5rem !important; font-weight: 400 !important; margin-bottom: 0.5rem !important; }
h2 { font-size: 1.75rem !important; font-weight: 400 !important; }
h3 { font-size: 1.25rem !important; font-weight: 400 !important; }
h4 { font-size: 1.05rem !important; font-weight: 400 !important; }

p, span, label, div:not(.stException) {
    font-family: var(--font-sans) !important;
    color: var(--ink);
}

/* ── Sidebar: dark editorial ── */
[data-testid="stSidebar"] {
    background: #1E1C28;
    border-right: none;
}
[data-testid="stSidebar"] * {
    color: #D4D0DC !important;
    font-family: var(--font-sans) !important;
}
[data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
    color: #FFFFFF !important;
    font-family: var(--font-display) !important;
}
[data-testid="stSidebar"] hr {
    border-color: rgba(255,255,255,0.08);
}
[data-testid="stSidebar"] .stButton > button {
    background: rgba(255,255,255,0.06) !important;
    border: 1px solid rgba(255,255,255,0.10) !important;
    color: #C4C0D0 !important;
    font-family: var(--font-sans) !important;
    border-radius: var(--radius) !important;
    transition: all 0.2s ease;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(255,255,255,0.12) !important;
    border-color: rgba(255,255,255,0.20) !important;
    color: #FFFFFF !important;
}

/* ── Top Navigation underline ── */
.nav-underline {
    border-bottom: 1px solid #E8E5E0;
    margin: -1rem 0 1.5rem 0;
}

/* ── Dashboard Cards ── */
.stats-row {
    display: flex;
    gap: 1rem;
    margin-bottom: 1.5rem;
}
.stat-card {
    flex: 1;
    background: var(--surface);
    padding: 1.5rem;
    border: 1px solid var(--border);
    box-shadow: var(--shadow-card);
}
.stat-card:first-child {
    border-left: 3px solid var(--indigo);
}
.stat-card .stat-number {
    font-family: var(--font-display);
    font-size: 2.5rem;
    color: var(--ink);
    line-height: 1;
    margin-bottom: 0.3rem;
}
.stat-card .stat-label {
    font-size: 0.8rem;
    color: var(--ink-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

/* ── Content cards ── */
.editorial-card {
    background: var(--surface);
    border: 1px solid var(--border);
    padding: 1.5rem;
    margin-bottom: 1rem;
    box-shadow: var(--shadow-card);
}
.editorial-card.accent-left {
    border-left: 3px solid var(--vermillion);
}

/* ── Material cards (grid) ── */
.material-grid-card {
    background: var(--surface);
    border: 1px solid var(--border);
    padding: 1.2rem;
    transition: all 0.2s ease;
    box-shadow: var(--shadow-card);
    height: 100%;
}
.material-grid-card:hover {
    border-color: var(--indigo);
    box-shadow: var(--shadow-elevated);
}
.material-grid-card .material-icon {
    font-size: 2rem;
    margin-bottom: 0.5rem;
}
.material-grid-card .material-name {
    font-weight: 600;
    font-size: 0.85rem;
    color: var(--ink);
    word-break: break-word;
}
.material-grid-card .material-meta {
    font-size: 0.75rem;
    color: var(--ink-muted);
    margin-top: 0.3rem;
}

/* ── Chat bubbles ── */
.interviewer-bubble {
    position: relative;
    background: #FDF5F3;
    border-left: 3px solid var(--vermillion);
    padding: 1rem 1.2rem;
    margin: 0.8rem 2rem 0.8rem 0;
    max-width: 90%;
}
.interviewer-bubble .bubble-speaker {
    font-family: var(--font-display);
    font-size: 0.8rem;
    color: var(--vermillion);
    margin-bottom: 0.4rem;
    letter-spacing: 0.02em;
}

.candidate-bubble {
    position: relative;
    background: #F4F3F8;
    border-right: 3px solid var(--indigo);
    padding: 1rem 1.2rem;
    margin: 0.8rem 0 0.8rem 2rem;
    max-width: 90%;
    margin-left: auto;
}
.candidate-bubble .bubble-speaker {
    font-family: var(--font-display);
    font-size: 0.8rem;
    color: var(--indigo);
    margin-bottom: 0.4rem;
    letter-spacing: 0.02em;
}

.system-bubble {
    background: var(--surface);
    border: 1px solid var(--border);
    padding: 1rem 1.2rem;
    margin: 0.6rem 0;
    box-shadow: var(--shadow-card);
}

/* ── Buttons ── */
.stButton > button {
    font-family: var(--font-sans) !important;
    font-weight: 500 !important;
    border-radius: var(--radius) !important;
    transition: all 0.2s ease !important;
    letter-spacing: 0.01em;
}
.stButton > button:hover {
    box-shadow: var(--shadow-elevated);
}
/* Primary button */
.stButton > button[kind="primary"] {
    background: var(--indigo) !important;
    border: none !important;
    color: #FFFFFF !important;
}
.stButton > button[kind="primary"]:hover {
    background: #3F3D6B !important;
}
/* Secondary/ghost */
.stButton > button[kind="secondary"] {
    background: transparent !important;
    border: 1px solid var(--border-strong) !important;
    color: var(--ink) !important;
}
.stButton > button[kind="secondary"]:hover {
    background: var(--indigo-light) !important;
    border-color: var(--indigo) !important;
    color: var(--indigo) !important;
}

/* ── Input fields ── */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div {
    border-radius: var(--radius) !important;
    border: 1px solid var(--border-strong) !important;
    font-family: var(--font-sans) !important;
    background: var(--surface) !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: var(--indigo) !important;
    box-shadow: 0 0 0 2px rgba(45,43,85,0.08) !important;
}

/* ── File uploader ── */
[data-testid="stFileUploader"] {
    border-radius: var(--radius) !important;
    border: 2px dashed var(--border-strong) !important;
    background: var(--surface) !important;
    padding: 1.5rem !important;
}
[data-testid="stFileUploader"]:hover {
    border-color: var(--indigo) !important;
    background: var(--indigo-light) !important;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    gap: 0 !important;
    border-bottom: 1px solid var(--border) !important;
}
.stTabs [data-baseweb="tab"] {
    font-family: var(--font-sans) !important;
    font-weight: 500 !important;
    font-size: 0.85rem !important;
    padding: 0.6rem 1.2rem !important;
    border-radius: 0 !important;
    color: var(--ink-light) !important;
}
.stTabs [aria-selected="true"] {
    color: var(--indigo) !important;
    border-bottom: 2px solid var(--indigo) !important;
}

/* ── Expander ── */
[data-testid="stExpander"] {
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    box-shadow: var(--shadow-card) !important;
}

/* ── Radio buttons ── */
.stRadio [data-baseweb="radio"] {
    font-family: var(--font-sans) !important;
}
.stRadio label {
    font-family: var(--font-sans) !important;
    color: var(--ink) !important;
}

/* ── Metrics ── */
[data-testid="stMetricValue"] {
    color: var(--ink) !important;
    font-family: var(--font-display) !important;
    font-weight: 400 !important;
}

/* ── Alerts ── */
.stAlert {
    border-radius: var(--radius) !important;
    border: none !important;
    font-family: var(--font-sans) !important;
    box-shadow: var(--shadow-card) !important;
}
.stAlert [data-testid="stNotificationContentError"] {
    border-left: 3px solid var(--vermillion) !important;
}
.stAlert [data-testid="stNotificationContentWarning"] {
    border-left: 3px solid var(--amber) !important;
}
.stAlert [data-testid="stNotificationContentSuccess"] {
    border-left: 3px solid var(--sage) !important;
}
.stAlert [data-testid="stNotificationContentInfo"] {
    border-left: 3px solid var(--indigo) !important;
}

/* ── Chat input ── */
[data-testid="stChatInput"] textarea {
    border-radius: var(--radius) !important;
    border: 1px solid var(--border-strong) !important;
    font-family: var(--font-sans) !important;
    background: var(--surface) !important;
}

/* ── Profile header ── */
.profile-hero {
    background: var(--indigo);
    color: #FFFFFF;
    padding: 1.5rem 2rem;
    margin-bottom: 1.5rem;
}
.profile-hero * { color: #FFFFFF !important; }
.profile-hero .profile-name {
    font-family: var(--font-display);
    font-size: 2rem;
    margin-bottom: 0.3rem;
}
.profile-hero .profile-role {
    font-family: var(--font-sans);
    font-size: 0.9rem;
    opacity: 0.8;
    font-weight: 400;
}

/* ── Setup section (interview config) ── */
.setup-section {
    background: var(--surface);
    border: 1px solid var(--border);
    padding: 1.5rem;
    margin-bottom: 1rem;
    box-shadow: var(--shadow-card);
}

/* ── Score ring (CSS-only) ── */
.score-display {
    display: flex;
    align-items: center;
    gap: 0.8rem;
}
.score-circle {
    width: 64px;
    height: 64px;
    border-radius: 50%;
    border: 3px solid var(--indigo);
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: var(--font-display);
    font-size: 1.5rem;
    color: var(--indigo);
    background: var(--surface);
}

/* ── Badges ── */
.tag {
    display: inline-block;
    padding: 0.2rem 0.7rem;
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-family: var(--font-sans);
}

.tag-resume { background: var(--indigo-light); color: var(--indigo); }
.tag-jd { background: var(--vermillion-light); color: var(--vermillion); }
.tag-project { background: var(--sage-light); color: var(--sage); }
.tag-image { background: var(--amber-light); color: var(--amber); }
.tag-active { background: #ECFDF5; color: #065F46; }
.tag-done { background: #F3F4F6; color: #6B7280; }

/* ── Empty state ── */
.empty-state {
    text-align: center;
    padding: 4rem 2rem;
    background: var(--surface);
    border: 2px dashed var(--border);
}
.empty-state .empty-icon {
    font-size: 3rem;
    margin-bottom: 1rem;
    opacity: 0.6;
}
.empty-state .empty-title {
    font-family: var(--font-display);
    font-size: 1.25rem;
    color: var(--ink);
    margin-bottom: 0.5rem;
}
.empty-state .empty-desc {
    font-size: 0.9rem;
    color: var(--ink-muted);
    max-width: 360px;
    margin: 0 auto;
}

/* ── History list ── */
.history-item {
    padding: 0.6rem 0;
    border-bottom: 1px solid var(--border);
    font-size: 0.85rem;
}
.history-item:last-child { border-bottom: none; }
.history-item .hi-date {
    color: var(--ink-muted);
    font-size: 0.75rem;
}
.history-item .hi-score {
    font-family: var(--font-display);
    color: var(--indigo);
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border-strong); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--ink-muted); }

/* ── Animation ── */
@keyframes fadeUp {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
}
.fade-up { animation: fadeUp 0.35s ease-out; }

/* ── Interview header bar ── */
.interview-header {
    background: var(--surface);
    border: 1px solid var(--border);
    border-left: 3px solid var(--vermillion);
    padding: 0.8rem 1.2rem;
    margin-bottom: 1rem;
    display: flex;
    align-items: center;
    gap: 1.5rem;
    font-size: 0.85rem;
    box-shadow: var(--shadow-card);
}
.interview-header .ih-stat {
    color: var(--ink-muted);
}
.interview-header .ih-stat strong {
    color: var(--ink);
}

/* ── Step indicator ── */
.step-row {
    display: flex;
    align-items: center;
    gap: 0;
    margin-bottom: 1.5rem;
}
.step-node {
    width: 28px; height: 28px;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.75rem; font-weight: 600;
    font-family: var(--font-sans);
}
.step-node.active { background: var(--indigo); color: #FFF; }
.step-node.done { background: var(--sage); color: #FFF; }
.step-node.pending { background: var(--border); color: var(--ink-muted); }
.step-bar {
    flex: 1; height: 1px;
    background: var(--border);
    margin: 0 0.5rem;
}
.step-bar.done { background: var(--sage); }

/* ── Responsive adjustments ── */
@media (max-width: 768px) {
    .stats-row { flex-direction: column; }
    h1 { font-size: 1.75rem !important; }
}
"""
