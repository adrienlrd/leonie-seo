"""Minimal, dependency-free Markdown → HTML for LLM-authored blog bodies.

The section generator asks for plain text, but the LLM still emits common Markdown
(`**bold**`, bullet lists, occasional links). Rendering the stored body verbatim
showed literal `**Confort**` to readers. This converts the realistic subset the
model produces — bold, italic, links, bullet/numbered lists, paragraphs and minor
headings — after HTML-escaping the raw text, so no merchant content can inject markup.
"""

from __future__ import annotations

import html
import re

_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITALIC_STAR = re.compile(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)")
_ITALIC_UNDERSCORE = re.compile(r"(?<![A-Za-z0-9_])_(?!\s)(.+?)(?<!\s)_(?![A-Za-z0-9_])")
_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+|/[^\s)]*)\)")
_BULLET = re.compile(r"^\s*[-*•]\s+(.*)$")
_NUMBERED = re.compile(r"^\s*\d+[.)]\s+(.*)$")
_HEADING = re.compile(r"^\s*(#{2,4})\s+(.*)$")


def render_inline_markdown(text: str) -> str:
    """Convert inline Markdown (bold, italic, links) in already-plain text to HTML."""
    escaped = html.escape(text or "", quote=False)
    escaped = _LINK.sub(r'<a href="\2">\1</a>', escaped)
    escaped = _BOLD.sub(r"<strong>\1</strong>", escaped)
    escaped = _ITALIC_STAR.sub(r"<em>\1</em>", escaped)
    escaped = _ITALIC_UNDERSCORE.sub(r"<em>\1</em>", escaped)
    return escaped


def render_markdown(text: str) -> str:
    """Convert a block of LLM Markdown to safe HTML (paragraphs, lists, headings)."""
    if not (text or "").strip():
        return ""
    blocks: list[str] = []
    para: list[str] = []
    list_items: list[str] = []
    list_tag = ""

    def flush_para() -> None:
        if para:
            blocks.append("<p>" + " ".join(para) + "</p>")
            para.clear()

    def flush_list() -> None:
        nonlocal list_tag
        if list_items:
            blocks.append(f"<{list_tag}>" + "".join(f"<li>{i}</li>" for i in list_items) + f"</{list_tag}>")
            list_items.clear()
            list_tag = ""

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            flush_para()
            flush_list()
            continue
        heading = _HEADING.match(line)
        if heading:
            flush_para()
            flush_list()
            level = min(len(heading.group(1)) + 1, 4)  # ## -> h3, ### -> h4, #### -> h4
            blocks.append(f"<h{level}>{render_inline_markdown(heading.group(2))}</h{level}>")
            continue
        bullet = _BULLET.match(line)
        numbered = _NUMBERED.match(line)
        if bullet or numbered:
            flush_para()
            tag = "ul" if bullet else "ol"
            if list_tag and list_tag != tag:
                flush_list()
            list_tag = tag
            content = (bullet or numbered).group(1)
            list_items.append(render_inline_markdown(content))
            continue
        flush_list()
        para.append(render_inline_markdown(line))

    flush_para()
    flush_list()
    return "\n".join(blocks)
