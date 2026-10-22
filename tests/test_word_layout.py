from docx import Document
from docx.oxml.ns import qn

from word_skills.render import append_content, default_document


def _draft(blocks):
    return {
        "title": "版式测试",
        "sections": [{"title": "正文", "blocks": blocks}],
    }


def test_table_rows_are_marked_unsplittable_and_header_repeats():
    doc = default_document()
    append_content(doc, _draft([
        {"type": "table", "headers": ["参数", "说明"],
         "rows": [["采样率", "每秒采集一次"]]},
    ]))

    table = doc.tables[0]
    assert table.cell(1, 0).text == "采样率"
    assert table.cell(1, 1).text == "每秒采集一次"
    assert table.rows[0]._tr.trPr.find(qn("w:tblHeader")) is not None
    assert all(row._tr.trPr.find(qn("w:cantSplit")) is not None for row in table.rows)
    # These OOXML properties request the behavior; only a rendered PDF can
    # establish how a particular Word/LibreOffice version paginates a long row.


def test_table_has_no_trailing_spacer_paragraph():
    doc = default_document()
    append_content(doc, _draft([
        {"type": "table", "headers": ["列"], "rows": [["值"]]},
    ]))

    body_children = list(doc.element.body)
    content_children = [node for node in body_children if node.tag != qn("w:sectPr")]
    assert content_children[-1].tag == qn("w:tbl")


def test_plain_paragraph_and_code_blocks_keep_backticks_verbatim():
    plain = "普通文本中的 `token` 保持原样"
    code = "print(`source backticks`)"
    doc = default_document()
    append_content(doc, _draft([
        {"type": "paragraph", "text": plain},
        {"type": "code", "text": code},
        {"type": "table", "headers": ["示例"], "rows": [["`table token`"]]},
    ]))

    assert plain in [p.text for p in doc.paragraphs]
    assert code in [p.text for p in doc.paragraphs]
    assert doc.tables[0].cell(1, 0).text == "`table token`"


def test_markdown_inline_code_is_opt_in_and_keeps_visible_text():
    doc = default_document()
    append_content(doc, _draft([
        {"type": "paragraph", "text": "运行 `python app.py` 即可。",
         "inline_format": "markdown"},
    ]))

    paragraph = doc.paragraphs[-1]
    assert paragraph.text == "运行 python app.py 即可。"
    code_runs = [run for run in paragraph.runs if run.font.name == "Consolas"]
    assert [run.text for run in code_runs] == ["python app.py"]
