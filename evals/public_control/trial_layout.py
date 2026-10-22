"""Re-render three recorded layout failures without editing historical runs."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from docx import Document
from word_skills.inline import inline_runs
from word_skills.inspect import inspect_docx, inspect_pdf, preview
from word_skills.render import render


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def table_text(path):
    return [[cell.text for row in table.rows for cell in row.cells] for table in Document(path).tables]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--soffice", required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    cases = [
        ("gin-table", "heldout-artifacts/gin-design-spec-heldout/G", False),
        ("flask-inline", "heldout-artifacts/flask-design-spec-heldout/B", True),
        ("express-table", "ablation-artifacts/express-technical-report-dev/S", False),
    ]
    results = []
    for name, relative, opt_inline in cases:
        source = args.source_root / "control" / relative
        target = args.out / name
        target.mkdir()
        original = json.loads((source / "draft.json").read_text(encoding="utf-8"))
        draft = copy.deepcopy(original)
        opted, skipped = [], []
        if opt_inline:
            for section in draft["sections"]:
                for block in section["blocks"]:
                    if block["type"] != "paragraph":
                        continue
                    try:
                        has_code = any(is_code for _text, is_code in inline_runs(block["text"]))
                    except ValueError:
                        skipped.append(block["id"])
                        continue
                    if has_code:
                        block["inline_format"] = "markdown"
                        opted.append(block["id"])
        write(target / "draft.json", draft)
        render(draft, target / "output.docx")
        check = inspect_docx(target / "output.docx", draft)
        renderer = preview(target / "output.docx", target / "preview", soffice=args.soffice)
        pdf = inspect_pdf(target / "preview/preview.pdf", draft)
        # The source JSON strings are never rewritten: only explicit formatting
        # metadata is added. Cells remain literal and preserve ordering/counts.
        stripped = copy.deepcopy(draft)
        for section in stripped["sections"]:
            for block in section["blocks"]:
                block.pop("inline_format", None)
        result = {
            "case": name, "scope": "formatter_regression_not_semantic_or_production_finalize",
            "before_directory": str(source), "before_draft_sha256": sha(source / "draft.json"),
            "before_docx_sha256": sha(source / "output.docx"),
            "before_pdf_sha256": sha(source / "preview/preview.pdf"),
            "after_draft_sha256": sha(target / "draft.json"),
            "body_strings_preserved": stripped == original,
            "table_cell_order_and_text_preserved": table_text(source / "output.docx") == table_text(target / "output.docx"),
            "opted_inline_blocks": opted, "unsupported_inline_blocks_left_literal": skipped,
            "docx_issues": check, "pdf_checks": pdf, "renderer": renderer,
            "visual_review": "pending_actual_page_inspection",
        }
        write(target / "manifest.json", result)
        results.append(result)
        print(json.dumps({"case": name, "pages": renderer["pages"], "docx_issues": len(check)}, ensure_ascii=False), flush=True)
    write(args.out / "summary.json", {"cases": results, "source_originals_edited": False})


if __name__ == "__main__":
    main()
