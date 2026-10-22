"""Build the E6 synthetic-layout fixture from pinned public project excerpts.

This is a document-conversion fixture, not an authored technical report or benchmark.
Run from the repository root with the project Python 3.12 environment.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor

REPO = Path(__file__).resolve().parents[2]
EXTERNAL = REPO.parent.parent / "word-skills-public-eval"
DATA = EXTERNAL / "data" / "fidelity-v1"
CONTROL = EXTERNAL / "control" / "fidelity-v1"
SOURCES = EXTERNAL / "data" / "formal-v1" / "sources" / "projects"

FASTAPI = SOURCES / "fastapi" / "raw" / "fastapi-993899cc2021daec7ba170c7ee9bcefd45e8db43"
EXPRESS_DOCS = SOURCES / "express-docs" / "raw" / "expressjs.com-dee32dd56b459db85de61691934e28adfc6502f8"
EXPRESS = SOURCES / "express" / "raw" / "express-0dee2c52c7c873498f8ed7d8ee4ddd0a04d3ada8"

SOURCES_META = {
    "fastapi": {"root": FASTAPI, "commit": "993899cc2021daec7ba170c7ee9bcefd45e8db43", "license": "MIT", "license_file": "LICENSE", "url": "https://github.com/fastapi/fastapi"},
    "express-docs": {"root": EXPRESS_DOCS, "commit": "dee32dd56b459db85de61691934e28adfc6502f8", "license": "CC-BY-4.0", "license_file": "LICENSE.md", "url": "https://github.com/expressjs/expressjs.com"},
    "express": {"root": EXPRESS, "commit": "0dee2c52c7c873498f8ed7d8ee4ddd0a04d3ada8", "license": "MIT", "license_file": "LICENSE", "url": "https://github.com/expressjs/express"},
}

# Public-source excerpts are short and deliberately repeated in a bounded fixture.
# Chinese prose is synthetic wrapper text; English excerpts remain verbatim.
EXCERPTS = [
    ("fastapi", "README.md", "FastAPI framework, high performance"),
    ("fastapi", "docs/en/docs/tutorial/first-steps.md", "The simplest FastAPI file could look like this"),
    ("fastapi", "docs/en/docs/tutorial/path-params.md", "You can declare path"),
    ("fastapi", "docs/en/docs/tutorial/query-params.md", "automatically interpreted as"),
    ("fastapi", "docs/en/docs/tutorial/body.md", "To declare a **request** body, you use"),
    ("fastapi", "docs/en/docs/tutorial/response-model.md", "In those cases, you can use the *path operation decorator* parameter"),
    ("express-docs", "src/content/docs/en/5x/guide/routing.mdx", "refers to how an application's endpoints"),
    ("express-docs", "src/content/docs/en/5x/guide/using-middleware.mdx", "Express is a routing and middleware"),
    ("express-docs", "src/content/docs/en/5x/guide/error-handling.mdx", "Error Handling_ refers to how Express catches"),
    ("express-docs", "src/content/docs/en/5x/guide/using-template-engines.mdx", "A _template engine_ enables"),
    ("express", "lib/application.js", "app.handle = function handle(req, res, callback)"),
    ("express", "lib/response.js", "res.send = function send(body) {"),
]

CHINESE = [
    "本页为公开项目摘录的中文排版夹具。中文说明是为版式测试编写的合成文字，不代表项目官方中文文档。",
    "摘录文字保留来源语义；仅用于检查转换后段落、表格、代码与定位信息是否可读。",
    "页内的字段名称、编号和公式是测试标记，不能据此推断完整产品行为或性能结论。",
    "表格列用于观察边框、单元格顺序与换行保存情况；不包含新的实测数据。",
]
ENGLISH = [
    "Synthetic layout fixture. The surrounding prose, identifiers, and tables were created to exercise document conversion, not to present a technical finding.",
    "Source excerpts are retained verbatim where marked. Interpret them only within the cited file and commit; this page is not a complete project specification.",
    "The page label and tabular values are fixture controls. They are not performance measurements or product claims.",
]

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()

def resolve_excerpt(source_id: str, rel: str, needle: str) -> dict:
    path = SOURCES_META[source_id]["root"] / rel
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    at = next((i for i, line in enumerate(lines) if needle.casefold() in line.casefold()), None)
    if at is None:
        raise ValueError(f"Source excerpt needle missing from pinned file: {source_id}:{rel}: {needle}")
    excerpt = lines[at].strip()
    if not excerpt:
        raise ValueError(f"Empty excerpt {source_id}:{rel}")
    # Keep the copy excerpt compact while preserving exact source text.
    excerpt = re.sub(r"\s+", " ", excerpt)
    return {"source_id": source_id, "path": rel, "commit": SOURCES_META[source_id]["commit"],
            "license": SOURCES_META[source_id]["license"], "url": SOURCES_META[source_id]["url"],
            "source_sha256": sha256(path), "line_start": at + 1, "line_end": at + 1,
            "excerpt": excerpt, "excerpt_sha256": hashlib.sha256(excerpt.encode()).hexdigest()}

def configure(doc: Document):
    sec = doc.sections[0]
    sec.top_margin = Inches(.62)
    sec.bottom_margin = Inches(.62)
    sec.left_margin = Inches(.7)
    sec.right_margin = Inches(.7)
    normal = doc.styles["Normal"]
    normal.font.name = "Aptos"
    normal.font.size = Pt(9)
    normal.paragraph_format.space_after = Pt(5)
    for s in ("Title", "Heading 1", "Heading 2"):
        doc.styles[s].font.name = "Aptos Display"
    doc.styles["Heading 1"].font.color.rgb = RGBColor(25, 72, 112)

def add_code(doc: Document, code: str):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(.18)
    p.paragraph_format.right_indent = Inches(.18)
    p.paragraph_format.space_before = Pt(3)
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run(code)
    r.font.name = "Consolas"
    r.font.size = Pt(8)

def source_code(excerpt: dict, index: int) -> str:
    if excerpt["source_id"] == "express":
        return f"// Source excerpt, page {index:02d}\n{excerpt['excerpt']}\n// line {excerpt['line_start']}"
    return f"# Source excerpt, page {index:02d}\n{excerpt['excerpt']}\n# source line {excerpt['line_start']}"

def build():
    DATA.mkdir(parents=True, exist_ok=True)
    CONTROL.mkdir(parents=True, exist_ok=True)
    (DATA / "page-images").mkdir(exist_ok=True)
    (DATA / "source-licenses").mkdir(exist_ok=True)
    (CONTROL / "ingest").mkdir(exist_ok=True)
    doc = Document()
    configure(doc)
    expected = []
    for idx in range(1, 25):
        layout = "zh" if idx <= 8 else "en" if idx <= 16 else "mixed"
        source_id, rel, needle = EXCERPTS[(idx - 1) % len(EXCERPTS)]
        src = resolve_excerpt(source_id, rel, needle)
        page_id = f"E6-P{idx:02d}"
        if idx > 1:
            doc.add_page_break()
        title = {"zh": f"合成版式样本 {idx:02d}｜来源摘录与结构保留", "en": f"Synthetic Layout Sample {idx:02d} | Source Excerpt and Structure", "mixed": f"样本 {idx:02d} / Sample {idx:02d} — Structured Source Excerpt"}[layout]
        doc.add_heading(title, level=1)
        label = f"{page_id} | synthetic_layout_from_public_sources | layout={layout}"
        p = doc.add_paragraph(label)
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        p.runs[0].italic = True
        p.runs[0].font.size = Pt(8)

        h = "1. 来源文本与范围" if layout == "zh" else "1. Source Text and Scope" if layout == "en" else "1. 来源文本 / Source Text"
        doc.add_heading(h, level=2)
        wrap = CHINESE[(idx - 1) % len(CHINESE)] if layout == "zh" else ENGLISH[(idx - 1) % len(ENGLISH)] if layout == "en" else CHINESE[(idx - 1) % len(CHINESE)] + " " + ENGLISH[(idx - 1) % len(ENGLISH)]
        doc.add_paragraph(wrap)
        doc.add_paragraph(src["excerpt"])
        scope = f"Source: {source_id}/{rel}, commit {src['commit']}, lines {src['line_start']}-{src['line_end']}, SHA-256 {src['source_sha256'][:16]}…"
        sp = doc.add_paragraph(scope)
        sp.runs[0].font.size = Pt(7)
        sp.runs[0].font.color.rgb = RGBColor(90, 90, 90)

        doc.add_heading("2. 字段映射 / Field Map", level=2)
        table = doc.add_table(rows=1, cols=3)
        table.style = "Light Shading Accent 1"
        headers = ["编号 / ID", "字段 / Field", "值 / Value"]
        for cell, value in zip(table.rows[0].cells, headers):
            cell.text = value
        rows = [[page_id, "layout", layout], ["S-" + f"{idx:02d}", "source_id", source_id], ["V-" + f"{idx:02d}", "fixture", "synthetic"]]
        for row in rows:
            cells = table.add_row().cells
            for cell, value in zip(cells, row):
                cell.text = value
                cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER

        doc.add_heading("3. 代码片段 / Code Fragment", level=2)
        code = source_code(src, idx)
        add_code(doc, code)

        doc.add_heading("4. 图示说明与公式 / Figure Caption and Formula", level=2)
        caption = f"图 {idx}. 合成流程示意：输入 → 解析 → 输出；该图注是 fixture 文本，不含项目原图。" if layout != "en" else f"Figure {idx}. Synthetic flow placeholder: input → parse → output; no original project image is embedded."
        doc.add_paragraph(caption)
        formula = f"L{idx} = text + table + code + caption"
        fp = doc.add_paragraph(formula)
        fp.runs[0].font.name = "Cambria Math"

        expected.append({"page_id": page_id, "page_number": idx, "layout": layout,
                         "classification": "synthetic_layout_from_public_sources",
                         "source": src, "expected": {"label": label, "wrapper_text": wrap,
                         "source_excerpt": src["excerpt"], "table": [headers, *rows], "code": code,
                         "caption": caption, "formula_text": formula}})
    doc.core_properties.title = "E6 synthetic layout fixture from public sources"
    doc.core_properties.subject = "Synthetic layout fixture; not a domain report or benchmark"
    doc.core_properties.comments = "synthetic_layout_from_public_sources; visual review pending"
    docx = DATA / "fidelity-fixture.docx"
    doc.save(docx)
    (CONTROL / "expected-pages.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in expected), encoding="utf-8")
    license_files = []
    for sid, meta in SOURCES_META.items():
        source_license = meta["root"] / meta["license_file"]
        target = DATA / "source-licenses" / f"{sid}-{meta['license_file']}"
        target.write_bytes(source_license.read_bytes())
        license_files.append({"source_id": sid, "license": meta["license"],
                              "source_path": meta["license_file"], "path": f"source-licenses/{target.name}",
                              "sha256": sha256(target)})
    manifest = {
        "fixture_id": "E6-synthetic-layout-v1", "classification": "synthetic_layout_from_public_sources",
        "description": "24-page programmatically assembled document fixture: 8 Chinese, 8 English, 8 mixed pages.",
        "not_a_benchmark": True, "visual_review_status": "pending",
        "inputs": [{k: v for k, v in SOURCES_META[sid].items() if k != "root"} for sid in SOURCES_META],
        "license_files": license_files,
        "source_excerpt_policy": "Short verbatim excerpts only; line-specific provenance and source file hashes recorded per page. Chinese explanatory wrapper text, page labels, tables, captions, and formulas are fixture-authored synthetic layout elements.",
        "omnidocbench_status": "blocked_unpaired_pages_no_score",
        "heldout_data_accessed": False,
        "outputs": {"docx": docx.name, "expected_pages": "../../control/fidelity-v1/expected-pages.jsonl"}
    }
    (DATA / "source-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"docx": str(docx), "pages": len(expected), "expected": len(expected)}, ensure_ascii=False))

if __name__ == "__main__":
    build()
