"""Rich markup → Streamlit rendering utilities."""
from __future__ import annotations
import re
from io import StringIO
from contextlib import contextmanager

from rich.console import Console


# ─── Rich markup → HTML / Markdown conversion ────────────

_RICH_TAGS = {
    r"\[bold\]": "<strong>",
    r"\[/bold\]": "</strong>",
    r"\[green\]": '<span style="color:green">',
    r"\[/green\]": "</span>",
    r"\[red\]": '<span style="color:red">',
    r"\[/red\]": "</span>",
    r"\[yellow\]": '<span style="color:#b8860b">',
    r"\[/yellow\]": "</span>",
    r"\[cyan\]": '<span style="color:#008b8b">',
    r"\[/cyan\]": "</span>",
    r"\[blue\]": '<span style="color:blue">',
    r"\[/blue\]": "</span>",
    r"\[magenta\]": '<span style="color:magenta">',
    r"\[/magenta\]": "</span>",
    r"\[dim\]": '<span style="opacity:0.6">',
    r"\[/dim\]": "</span>",
    r"\[bold green\]": '<strong style="color:green">',
    r"\[/bold green\]": "</strong>",
    r"\[bold red\]": '<strong style="color:red">',
    r"\[/bold red\]": "</strong>",
    r"\[bold yellow\]": '<strong style="color:#b8860b">',
    r"\[/bold yellow\]": "</strong>",
    r"\[bold cyan\]": '<strong style="color:#008b8b">',
    r"\[/bold cyan\]": "</strong>",
    r"\[bold magenta\]": '<strong style="color:magenta">',
    r"\[/bold magenta\]": "</strong>",
}


def rich_to_html(text: str) -> str:
    """Convert rich markup tags to HTML."""
    for tag, html in _RICH_TAGS.items():
        text = re.sub(tag, html, text)
    return text


def rich_to_text(text: str) -> str:
    """Strip rich markup tags, return plain text."""
    for tag in _RICH_TAGS:
        text = re.sub(tag, "", text)
    return text


# ─── Console capture ──────────────────────────────────────

@contextmanager
def capture_console(skill_module):
    """Context manager to capture rich console output from a skill module.

    Usage:
        import skills.material
        with capture_console(skills.material) as buf:
            material_skill.run("list", "")
        output = buf.getvalue()
    """
    capture = StringIO()
    old_console = skill_module.console
    skill_module.console = Console(
        file=capture,
        force_terminal=False,
        width=100,
        color_system=None,
    )
    try:
        yield capture
    finally:
        skill_module.console = old_console
