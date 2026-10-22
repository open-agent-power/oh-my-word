import copy
import importlib

import pytest

from word_skills.evidence import block_text
from word_skills.inline import display_text, inline_runs
from word_skills.inspect import inspect_docx
from word_skills.models import validate_draft_v1, validate_renderable_draft
from word_skills.render import render


def draft():
    return {"schema_version": 1, "mode": "technical-report", "title": "结构检查",
            "sections": [{"id": "s", "title": "正文", "blocks": [
                {"id": "b", "type": "paragraph", "text": "确认的正文"}]}]}


@pytest.mark.parametrize("mutate, location", [
    (lambda d: d["sections"][0].pop("blocks"), r"sections\[0\].blocks"),
    (lambda d: d["sections"][0].update(blocks=[]), r"sections\[0\].blocks"),
    (lambda d: d["sections"][0].pop("title"), r"sections\[0\].title"),
    (lambda d: d["sections"][0]["blocks"][0].pop("text"), r"blocks\[0\].text"),
    (lambda d: d["sections"][0]["blocks"][0].update(type="unknown"), r"blocks\[0\].type"),
    (lambda d: d.update(sections=[]), "draft.sections"),
])
def test_missing_renderer_fields_rejected_before_output_or_template(tmp_path, monkeypatch, mutate, location):
    value = draft()
    mutate(value)
    snapshot = copy.deepcopy(value)
    renderer = importlib.import_module("word_skills.render")
    monkeypatch.setattr(renderer, "fingerprint", lambda _p: pytest.fail("invalid draft reached template IO"))
    output = tmp_path / "invalid.docx"
    with pytest.raises(ValueError, match=location):
        render(value, output, template=tmp_path / "template.docx")
    assert value == snapshot
    assert not output.exists()


@pytest.mark.parametrize("table, location", [
    ({"headers": [], "rows": [["text"]]}, "nonempty"),
    ({"headers": ["A", "B"], "rows": [["only one"]]}, r"rows\[0\]"),
    ({"headers": ["A"], "rows": [["value"]], "widths": [0]}, "widths"),
    ({"headers": ["A"], "rows": [["value"]], "widths": [float("nan")]}, "widths"),
    ({"headers": ["A", "B"], "rows": [["x", "y"]], "widths": [1e308, 1e308]}, "widths"),
    ({"headers": ["A"], "rows": [["value"]], "widths": [True]}, "widths"),
])
def test_table_shape_cannot_silently_drop_cells_or_make_invalid_widths(table, location):
    value = draft()
    value["sections"][0]["blocks"] = [{"type": "table", **table}]
    with pytest.raises(ValueError, match=location):
        validate_renderable_draft(value)


def test_valid_contract_is_not_rewritten_and_renderer_neutral_stays_supported():
    value = draft()
    snapshot = copy.deepcopy(value)
    assert validate_draft_v1(value) is value
    assert value == snapshot
    neutral = {key: value[key] for key in ("title", "sections")}
    assert validate_renderable_draft(neutral) is neutral


def test_explicit_inline_code_matches_renderer_and_inspector(tmp_path):
    value = draft()
    block = value["sections"][0]["blocks"][0]
    block.update(text="调用 `request.body()` 返回原始字节。", inline_format="markdown")
    snapshot = copy.deepcopy(value)
    assert block_text(block) == "调用 request.body() 返回原始字节。"
    output = tmp_path / "inline.docx"
    render(value, output)
    assert inspect_docx(output, value) == []
    assert value == snapshot


@pytest.mark.parametrize("text", ["**不支持的加粗**", "[link](https://example.test)", "<b>HTML</b>"])
def test_unsupported_opt_in_markup_fails_instead_of_silently_losing_structure(text):
    value = draft()
    block = value["sections"][0]["blocks"][0]
    block.update(text=text, inline_format="markdown")
    with pytest.raises(ValueError, match="inline_format"):
        validate_renderable_draft(value)


def test_plain_and_source_text_are_never_interpreted_as_markup():
    literal = "`code` **emphasis** <tag>"
    assert display_text({"type": "paragraph", "text": literal}) == literal
    assert display_text({"type": "code", "text": literal}) == literal
    assert inline_runs("使用 ``a`b`` 表示反引号。") == [("使用 ", False), ("a`b", True), (" 表示反引号。", False)]


def test_inline_format_cannot_be_attached_to_source_code():
    value = draft()
    value["sections"][0]["blocks"][0].update(type="code", inline_format="markdown")
    with pytest.raises(ValueError, match="inline_format"):
        validate_renderable_draft(value)


def test_build_rejects_missing_content_without_creating_delivery(tmp_path):
    import json
    from word_skills.delivery import build

    value = draft()
    value["sections"][0].pop("blocks")
    path = tmp_path / "bad-draft.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    output = tmp_path / "delivery"
    with pytest.raises(ValueError, match=r"sections\[0\].blocks"):
        build(path, tmp_path / "unread-case", output)
    assert not output.exists()
