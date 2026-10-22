"""Explicit, bounded inline-code formatting; ordinary text remains literal."""
from __future__ import annotations

from markdown_it import MarkdownIt


def inline_runs(text: str) -> list[tuple[str, bool]]:
    """Parse text and CommonMark code spans, rejecting unsupported formatting.

    Code-span whitespace follows CommonMark. No HTML, links, images, emphasis,
    or other Markdown structure is silently removed or interpreted.
    """
    tokens = MarkdownIt("commonmark").parseInline(text)[0].children or []
    runs = []
    for token in tokens:
        if token.type in {"text", "code_inline"}:
            runs.append((token.content, token.type == "code_inline"))
        elif token.type == "softbreak":
            runs.append(("\n", False))
        else:
            raise ValueError(f"Unsupported inline Markdown token: {token.type}; only text and code spans are supported")
    return runs


def display_text(block: dict) -> str:
    """Return exactly the visible paragraph text used by the Word renderer."""
    text = block.get("text", "")
    if block.get("inline_format") == "markdown":
        if block.get("type") != "paragraph":
            raise ValueError("inline_format=markdown is supported only for paragraphs")
        return "".join(value for value, _code in inline_runs(text))
    return text
