"""Offline ingestion with immutable snapshots and explicit conversion loss notices."""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from zipfile import ZipFile
from defusedxml import ElementTree

from .common import check_docx, now, sha256, write_json

TEXT_EXTENSIONS = {".md", ".txt", ".py", ".pyw", ".java", ".xml", ".json", ".yaml", ".yml", ".toml", ".properties", ".js", ".ts", ".sql", ".csv", ".jsx", ".tsx", ".kt", ".kts", ".go", ".rs", ".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".cs", ".swift", ".php", ".rb", ".scala", ".sh", ".bash", ".ps1", ".vue", ".svelte", ".html", ".css"}
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "target", "__pycache__", ".tools", "outputs", ".agent"}


def extract(path, *, force_text=False):
    path = Path(path)
    notices = []
    if force_text or path.suffix.lower() in TEXT_EXTENSIONS:
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            text = path.read_text(encoding="gb18030")
            notices.append("Decoded using GB18030; verify against original")
        if "\x00" in text:
            raise ValueError("Binary content detected in text file")
        return text, [{"locator": f"L{i}", "text": s} for i, s in enumerate(text.splitlines(), 1)], notices
    if path.suffix.lower() not in {".docx", ".pdf"}:
        raise ValueError(f"Unsupported input: {path.suffix}")
    if path.suffix.lower() == ".docx":
        check_docx(path)
    from markitdown import MarkItDown
    converted = MarkItDown(enable_plugins=False).convert_local(str(path))
    text = converted.text_content
    notices.append("Converted Markdown is for reading, not a layout-preserving copy")
    segments = []
    if path.suffix.lower() == ".docx":
        from docx import Document
        from docx.table import Table
        from docx.text.paragraph import Paragraph
        doc = Document(path)
        for i, item in enumerate(doc.iter_inner_content(), 1):
            if isinstance(item, Paragraph):
                segments.append({"locator": f"body/{i}", "text": item.text})
            elif isinstance(item, Table):
                for r, row in enumerate(item.rows, 1):
                    segments.append({"locator": f"body/{i}/row/{r}", "text": " | ".join(c.text for c in row.cells)})
        with ZipFile(path) as z:
            xml = ElementTree.fromstring(z.read("word/document.xml"))
            tags = {element.tag.split("}")[-1] for element in xml.iter()}
            for marker, label in [("oMath", "Formula"), ("drawing", "Image"), ("txbxContent", "Text box"), ("ins", "Tracked change"), ("del", "Tracked change")]:
                if marker in tags:
                    notices.append(f"{label} present; inspect original, text extraction may omit details")
        notices.append("Headers, footers, notes and embedded objects are not evidence segments in v1")
    else:
        from pypdf import PdfReader
        for i, page in enumerate(PdfReader(path).pages, 1):
            page_text = page.extract_text() or ""
            segments.append({"locator": f"page/{i}", "text": page_text})
            if not page_text.strip():
                notices.append(f"Page {i} has no extracted text; OCR/original review required")
    if not text.strip():
        notices.append("No readable text; this source cannot support text claims")
    return text, segments, notices


def ingest(inputs, case, *, text_inputs=()):
    case = Path(case).resolve()
    text_inputs = {Path(p).resolve() for p in text_inputs}
    if (case / "source-index.json").exists():
        raise ValueError("Case already indexed; use a new case directory to preserve evidence")
    files, skipped = [], []
    for raw in inputs:
        path = Path(raw).resolve()
        if not path.exists():
            raise ValueError(f"Missing input: {path}")
        if case == path or case.is_relative_to(path):
            raise ValueError("Case output must be outside the input tree")
        if path.is_dir():
            candidates = []
            for current, dirs, names in os.walk(path, topdown=True, followlinks=False):
                folder = Path(current)
                # Prune before descending; filtering rglob results still walks dependencies.
                dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not (folder / d).is_symlink())
                candidates.extend(folder / name for name in names)
            candidates.sort()
        else:
            candidates = [path]
        for candidate in candidates:
            relparts = candidate.relative_to(path).parts if path.is_dir() else (candidate.name,)
            if any(p in SKIP_DIRS for p in relparts):
                continue
            if not candidate.is_file():
                continue
            if candidate.is_symlink() or not candidate.resolve().is_relative_to(path if path.is_dir() else path.parent):
                skipped.append({"path": str(candidate), "reason": "Symlink/outside input root"})
            elif candidate.name.startswith(".env") or candidate.suffix.lower() in {".pem", ".key", ".pfx"}:
                skipped.append({"path": str(candidate), "reason": "Potential credential file"})
            elif candidate.suffix.lower() not in TEXT_EXTENSIONS | {".docx", ".pdf"} and candidate.resolve() not in text_inputs:
                skipped.append({"path": str(candidate), "reason": "Unsupported format; not silently consumed"})
            elif candidate.stat().st_size > 20_000_000:
                skipped.append({"path": str(candidate), "reason": "File larger than 20 MB"})
            else:
                files.append(candidate)
    sources = []
    for number, path in enumerate(dict.fromkeys(files), 1):
        sid = f"S{number:03d}"
        folder = case / "sources" / sid
        folder.mkdir(parents=True, exist_ok=True)
        snapshot = folder / ("original" + path.suffix)
        shutil.copyfile(path, snapshot)
        try:
            text, segments, notices = (extract(snapshot, force_text=True)
                                       if path.resolve() in text_inputs else extract(snapshot))
        except Exception as exc:
            skipped.append({"path": str(path), "reason": f"Extraction failed: {type(exc).__name__}: {exc}"})
            continue
        extracted = folder / "extracted.md"
        extracted.write_text(text, encoding="utf-8")
        segments_path = folder / "segments.json"
        write_json(segments_path, segments)
        sources.append({"id": sid, "original_path": str(path), "snapshot": snapshot.relative_to(case).as_posix(),
                        "sha256": sha256(snapshot), "extracted": extracted.relative_to(case).as_posix(),
                        "extracted_sha256": sha256(extracted), "segments": segments_path.relative_to(case).as_posix(),
                        "segments_sha256": sha256(segments_path), "notices": notices})
    result = {"schema_version": 1, "created_at": now(), "sources": sources, "skipped": skipped}
    write_json(case / "source-index.json", result)
    write_json(case / "evidence.json", {"schema_version": 1, "claims": []})
    return result
