"""Render the generated fidelity PDF to per-page PNGs via bundled PDFium."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pypdfium2 as pdfium

REPO = Path(__file__).resolve().parents[2]
EXTERNAL = REPO.parent.parent / "word-skills-public-eval"
DATA = EXTERNAL / "data" / "fidelity-v1"

def main():
    pdf_path = DATA / "fidelity-fixture.pdf"
    out = DATA / "page-images"
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.png"):
        old.unlink()
    doc = pdfium.PdfDocument(str(pdf_path))
    rows = []
    for i in range(len(doc)):
        path = out / f"page-{i + 1:02d}.png"
        doc[i].render(scale=120 / 72).to_pil().save(path)
        h = hashlib.sha256(path.read_bytes()).hexdigest()
        rows.append({"page_number": i + 1, "path": f"page-images/{path.name}", "sha256": h})
    (DATA / "page-render-manifest.json").write_text(json.dumps({
        "renderer": "pypdfium2", "dpi": 120, "pdf": "fidelity-fixture.pdf",
        "pages": len(doc), "visual_review_status": "pending", "images": rows
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"renderer": "pypdfium2", "pages": len(rows), "pngs": len(rows)}))

if __name__ == "__main__":
    main()
