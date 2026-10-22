"""Preserve the upstream Markdown manual using markdown-it and the shared renderer."""
from pathlib import Path
import shutil

from markdown_it import MarkdownIt

from .common import inside, sha256


def markdown_blocks(text, attachments, source_root, case):
    """Images must be declared business attachments, copied to the audited case."""
    declared = {inside(source_root, item["path"]): item for item in attachments}
    tokens = MarkdownIt("commonmark").enable("table").parse(text)
    blocks, index = [], 0
    list_items = []

    # Reject unsupported markup before copying any image or projecting content.
    for token in tokens:
        if token.type == "html_block" or any(c.type == "html_inline" for c in token.children or []):
            line = token.map[0] + 1 if token.map else "unknown"
            raise ValueError(f"Raw HTML in manual at line {line} is not supported; use Markdown paragraphs/tables/images")

    def add(kind, **fields):
        if list_items and list_items[-1]["pending"]:
            item = list_items[-1]
            item["pending"] = False
            if kind == "paragraph" and not fields.get("monospace"):
                fields["text"] = item["marker"] + (" " + fields["text"] if fields["text"] else "")
            else:
                add("paragraph", text=item["marker"])
        blocks.append({"id": f"manual-{len(blocks)}", "type": kind, "intent": "fact",
                       "claim_ids": ["manual-transcription"], **fields})

    def plain(token):
        if not token.children:
            return token.content
        return "".join("\n" if c.type in {"softbreak", "hardbreak"} else c.content
                       for c in token.children if c.type in {"text", "code_inline", "softbreak", "hardbreak"})

    while index < len(tokens):
        token = tokens[index]
        if token.type == "list_item_open":
            # Keep the literal marker, including start offsets and repeated "1.".
            # Generated counters would introduce numbers absent from the evidence.
            if list_items and list_items[-1]["pending"]:
                add("paragraph", text="")
            list_items.append({"marker": "  " * len(list_items) + token.info + token.markup, "pending": True})
        elif token.type == "list_item_close":
            if list_items[-1]["pending"]:
                add("paragraph", text="")
            list_items.pop()
        elif token.type == "heading_open":
            add("paragraph", text=plain(tokens[index + 1]), heading_level=min(3, int(token.tag[1:])))
            index += 3
            continue
        if token.type in {"fence", "code_block"}:
            add("paragraph", text=token.content.rstrip("\n"), monospace=True)
        elif token.type == "inline":
            images = [c for c in token.children or [] if c.type == "image"]
            content = plain(token)
            if content.strip():
                add("paragraph", text=content)
            for image in images:
                requested = image.attrGet("src") or ""
                original = inside(source_root, requested)
                if original not in declared or original.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
                    raise ValueError("manual image must be a declared local PNG/JPEG screenshot")
                checksum = sha256(original)
                relative = f"assets/{checksum}{original.suffix.lower()}"
                target = inside(case, relative)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(original, target)
                add("image", text=image.content or declared[original]["feature"],
                    path=relative, sha256=checksum)
        elif token.type == "table_open":
            rows, row = [], []
            index += 1
            while tokens[index].type != "table_close":
                cell = tokens[index]
                if cell.type == "tr_open":
                    row = []
                elif cell.type == "inline":
                    if any(c.type == "image" for c in cell.children or []):
                        raise ValueError("Put manual images in standalone paragraphs, not table cells")
                    row.append(plain(cell))
                elif cell.type == "tr_close":
                    rows.append(row)
                index += 1
            if len(rows) > 1:
                add("table", headers=rows[0], rows=rows[1:])
        index += 1
    return blocks
