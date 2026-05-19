"""Minimal CSS — only for custom HTML elements Streamlit cannot style natively."""
from __future__ import annotations

THEME_CSS = """
/* ── Chat bubbles ── */
.interviewer-bubble {
    background: #FEF2F2;
    border-left: 3px solid #EF4444;
    padding: 0.75rem 1rem;
    margin: 0.5rem 0;
    border-radius: 4px;
}
.interviewer-bubble .bubble-speaker {
    font-size: 0.75rem;
    font-weight: 600;
    color: #DC2626;
    margin-bottom: 0.25rem;
}

.candidate-bubble {
    background: #EEF2FF;
    border-left: 3px solid #5E6AD2;
    padding: 0.75rem 1rem;
    margin: 0.5rem 0;
    border-radius: 4px;
}
.candidate-bubble .bubble-speaker {
    font-size: 0.75rem;
    font-weight: 600;
    color: #5E6AD2;
    margin-bottom: 0.25rem;
}

/* ── Interview status bar ── */
.interview-bar {
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-left: 3px solid #5E6AD2;
    padding: 0.6rem 1rem;
    margin-bottom: 1rem;
    border-radius: 4px;
}
"""
