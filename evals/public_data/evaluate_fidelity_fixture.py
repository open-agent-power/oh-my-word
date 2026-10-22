"""Run the existing ingest/MarkItDown extraction path on the E6 fixture."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EXTERNAL = REPO.parent.parent / "word-skills-public-eval"
DATA = EXTERNAL / "data" / "fidelity-v1"
CONTROL = EXTERNAL / "control" / "fidelity-v1"
OUT = CONTROL / "ingest"
sys.path.insert(0, str(REPO))

from word_skills.ingest import extract  # noqa: E402

def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    expected = [json.loads(x) for x in (CONTROL / "expected-pages.jsonl").read_text(encoding="utf-8").splitlines()]
    docx_text, docx_segments, docx_notices = extract(DATA / "fidelity-fixture.docx")
    pdf_text, pdf_segments, pdf_notices = extract(DATA / "fidelity-fixture.pdf")
    (OUT / "markitdown-docx.md").write_text(docx_text, encoding="utf-8")
    (OUT / "markitdown-pdf.md").write_text(pdf_text, encoding="utf-8")
    (OUT / "docx-segments.json").write_text(json.dumps(docx_segments, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "pdf-page-segments.json").write_text(json.dumps(pdf_segments, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    pages = []
    component_total = component_passed = chars_expected = chars_retained = 0
    for row in expected:
        number = row["page_number"]
        segment = next((x for x in pdf_segments if x["locator"] == f"page/{number}"), None)
        extracted = segment["text"] if segment else ""
        haystack = norm(extracted)
        e = row["expected"]
        components = {"label": e["label"], "wrapper_text": e["wrapper_text"],
                      "source_excerpt": e["source_excerpt"], "code": e["code"],
                      "caption": e["caption"], "formula_text": e["formula_text"]}
        components.update({f"table_cell_{ri}_{ci}": cell
                           for ri, table_row in enumerate(e["table"])
                           for ci, cell in enumerate(table_row)})
        component_results = {}
        for key, value in components.items():
            target = norm(value)
            ok = bool(target and target in haystack)
            component_results[key] = {"present": ok, "expected": value}
            component_total += 1
            component_passed += int(ok)
            # Character recall is reported as supporting detail only.
            chars_expected += len(target)
            chars_retained += sum(1 for ch in target if ch in haystack)
        rows_ok = 0
        for table_row in e["table"]:
            vals = [norm(c) for c in table_row]
            rows_ok += int(all(v in haystack for v in vals))
        pages.append({"page_id": row["page_id"], "page_number": number,
                      "layout": row["layout"], "extracted_chars": len(extracted),
                      "component_count": len(components),
                      "components_exactly_present": sum(x["present"] for x in component_results.values()),
                      "component_loss_count": sum(not x["present"] for x in component_results.values()),
                      "table_rows_expected": len(e["table"]), "table_rows_all_cells_present": rows_ok,
                      "components": component_results})
    (OUT / "page-metrics.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in pages), encoding="utf-8")

    page_image_files = sorted((DATA / "page-images").glob("page-*.png"))
    report = {
        "fixture_id": "E6-synthetic-layout-v1", "classification": "synthetic_layout_from_public_sources",
        "ingest_path": "word_skills.ingest.extract -> MarkItDown (plugins disabled); PDF page text segments from pypdf inside same path",
        "pages_expected": len(expected), "pdf_pages_extracted": len(pdf_segments),
        "page_images": len(page_image_files), "page_images_visual_review": "pending",
        "component_exact_presence": {"passed": component_passed, "total": component_total,
                                      "rate": round(component_passed / component_total, 6) if component_total else None,
                                      "loss_count": component_total - component_passed},
        "character_recall_supporting": round(chars_retained / chars_expected, 6) if chars_expected else None,
        "per_page": pages,
        "conversion_notices": {"docx": docx_notices, "pdf": pdf_notices},
        "scope": ["Checks literal presence of expected page labels, synthetic wrapper text, source excerpt, table cell values, code, caption, and formula in PDF page extraction.",
                  "This is a content-preservation smoke test, not a semantic-accuracy, OCR, accessibility, or layout-quality score.",
                  "Expected values describe the synthetic fixture itself; no real benchmark answer, OmniDocBench page, CMRC question, or heldout gold was used."],
        "failure_conditions": ["Missing component or table-cell row lowers exact-presence coverage.",
                               "Page count mismatch is reported separately; cross-page spill can cause per-page exact misses."],
        "artifacts": {"docx_sha256": sha256(DATA / "fidelity-fixture.docx"),
                      "pdf_sha256": sha256(DATA / "fidelity-fixture.pdf"),
                      "page_metrics": "page-metrics.jsonl", "markitdown_docx": "markitdown-docx.md",
                      "markitdown_pdf": "markitdown-pdf.md", "expected_pages": "../expected-pages.jsonl",
                      "page_images": [f"../../data/fidelity-v1/page-images/{p.name}" for p in page_image_files]},
    }
    (OUT / "metrics.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md = ["# E6 fixture extraction report", "", f"- Pages: {len(expected)} expected; {len(pdf_segments)} extracted; {len(page_image_files)} PNG renders.",
          f"- Exact component presence: {component_passed}/{component_total} ({report['component_exact_presence']['rate']:.1%}); missing {component_total-component_passed}.",
          f"- Supporting character recall: {report['character_recall_supporting']:.1%}.", "- Visual review: pending.", "- Classification: `synthetic_layout_from_public_sources`; not a domain report or benchmark score.", "",
          "## Page coverage", "", "| Page | Layout | Components present | Loss | Table rows with all cells |", "|---:|---|---:|---:|---:|"]
    md += [f"| {p['page_number']} | {p['layout']} | {p['components_exactly_present']}/{p['component_count']} | {p['component_loss_count']} | {p['table_rows_all_cells_present']}/{p['table_rows_expected']} |" for p in pages]
    md += ["", "## Scope", "", *[f"- {s}" for s in report["scope"]], "", "## Conversion notices", "", "```json", json.dumps(report["conversion_notices"], ensure_ascii=False, indent=2), "```", ""]
    (OUT / "report.md").write_text("\n".join(md), encoding="utf-8")
    print(json.dumps({"pdf_pages": len(pdf_segments), "pngs": len(page_image_files), "components": f"{component_passed}/{component_total}", "loss": component_total-component_passed}, ensure_ascii=False))

if __name__ == "__main__":
    main()
