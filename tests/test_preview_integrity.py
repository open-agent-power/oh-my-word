"""PDF extraction and isolated preview invariants; no real Office claim in mocks."""
from pathlib import Path
from types import SimpleNamespace

import pytest
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

from word_skills.common import sha256
from word_skills.inspect import inspect_pdf, preview


def test_pdf_content_omission_is_detected(tmp_path):
    path = tmp_path / "blank.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    writer.write(path)
    draft = {"title": "Missing title", "sections": [{"id": "s", "title": "Heading", "blocks": [
        {"id": "p", "type": "paragraph", "text": "Body absent"},
        {"id": "t", "type": "table", "headers": ["Name"], "rows": [["Value"]]},
    ]}]}
    result = inspect_pdf(path, draft)
    assert {i["location"] for i in result["issues"] if i["code"] == "PDF_CONTENT"} == {"title", "s"}
    assert {i["location"] for i in result["issues"] if i["code"] == "PDF_CONTENT_REVIEW"} == {"p", "t"}


def table_pdf(path, borders=True):
    """Real PDF with both columns wrapping on the same visual lines."""
    writer = PdfWriter()
    page = writer.add_blank_page(width=595, height=842)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                             NameObject("/Subtype"): NameObject("/Type1"),
                             NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
    commands = []
    for x, y, text in [(50, 800, "Title"), (50, 770, "Heading"),
                       (55, 730, "ColumnA"), (305, 730, "ColumnB"),
                       (55, 700, "long left cell"), (305, 700, "long right cell"),
                       (55, 685, "continued left cell"), (305, 685, "continued right cell")]:
        commands.append(f"BT /F1 10 Tf {x} {y} Td ({text}) Tj ET")
    if borders:
        commands += [f"{x} 670 m {x} 750 l S" for x in (50, 300, 550)]
        commands += [f"50 {y} m 550 {y} l S" for y in (670, 715, 750)]
    stream = DecodedStreamObject()
    stream.set_data("\n".join(commands).encode("ascii"))
    page[NameObject("/Contents")] = writer._add_object(stream)
    writer.write(path)


def table_draft(count=1):
    return {"title": "Title", "sections": [{"id": "s", "title": "Heading", "blocks": [
        {"id": "t", "type": "table", "headers": ["ColumnA", "ColumnB"],
         "rows": [["long left cell continued left cell", "long right cell continued right cell"] for _ in range(count)]}]}]}


def test_real_pdf_wrapped_columns_use_spatial_cells(tmp_path):
    path = tmp_path / "table.pdf"
    table_pdf(path)
    assert not inspect_pdf(path, table_draft())["issues"]


def test_real_pdf_missing_repeated_rows_requires_review(tmp_path):
    path = tmp_path / "table.pdf"
    table_pdf(path)
    issues = inspect_pdf(path, table_draft(65))["issues"]
    assert len(issues) == 1
    assert issues[0]["code"] == "PDF_CONTENT_REVIEW"
    assert "64 required" in issues[0]["message"]


def test_real_pdf_borderless_interleaving_is_reviewable(tmp_path):
    path = tmp_path / "table.pdf"
    table_pdf(path, borders=False)
    issues = inspect_pdf(path, table_draft())["issues"]
    assert issues and all(i["severity"] == "warning" for i in issues)


def test_existing_preview_is_not_reused(tmp_path):
    (tmp_path / "page-1.png").write_bytes(b"stale image")
    with pytest.raises(ValueError, match="already exist"):
        preview(tmp_path / "input.docx", tmp_path, "soffice", "pdftoppm")


def test_preview_rasterizes_in_isolated_directory_and_records_provenance(tmp_path, monkeypatch):
    source = tmp_path / "input.docx"
    source.write_bytes(b"mock docx")
    tools = []
    for name in ("soffice", "pdftoppm"):
        tool = tmp_path / name
        tool.write_bytes(name.encode())
        tools.append(tool)
    out = tmp_path / "out"
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        if "--convert-to" in args:
            folder = Path(args[args.index("--outdir") + 1])
            pdf = PdfWriter()
            pdf.add_blank_page(width=595, height=842)
            pdf.write(folder / "input.pdf")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if "-png" in args:
            assert Path(args[-2]).parent != out
            assert Path(args[-1]).parent == Path(args[-2]).parent
            Path(args[-1] + "-1.png").write_bytes(b"mock raster result")
            return SimpleNamespace(returncode=0)
        return SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr("word_skills.inspect.subprocess.run", run)
    result = preview(source, out, *tools)
    assert result["version"] is None
    assert result["provenance"]["pdf_sha256"] == sha256(out / "preview.pdf")
    assert result["provenance"]["page_hashes"] == {"page-1.png": sha256(out / "page-1.png")}
    assert result["provenance"]["docx_sha256"] == sha256(source)
    assert not Path(calls[0][calls[0].index("--outdir") + 1]).exists()
