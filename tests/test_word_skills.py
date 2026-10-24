import json
from pathlib import Path

import pytest
import yaml

from word_skills.cli import main
from word_skills.models import CaseManifest, Fact, Source, to_dict, validate_draft_v1
from word_skills.registry import load_registry
from word_skills.router import list_skills, route


ROOT = Path(__file__).resolve().parents[1]


def test_packaged_registry_snapshot_matches_source_of_truth():
    assert (ROOT / "word_skills/data/skills.yaml").read_text(encoding="utf-8") == (
        ROOT / "registry/skills.yaml"
    ).read_text(encoding="utf-8")


def test_registry_has_six_implemented_skills():
    rows = load_registry(ROOT)
    assert {row["name"] for row in rows} == {
        "word-skills", "oh-my-technology", "oh-my-patent", "word-document",
        "oh-my-proposal", "oh-my-copyright",
    }
    assert {row["status"] for row in rows} == {"implemented"}
    assert all(row["path"] for row in rows)


def test_technology_modes_have_explicit_focus_scope():
    technology = next(row for row in load_registry(ROOT) if row["name"] == "oh-my-technology")
    assert technology["mode_scope"] == {
        "technical-report": "focused",
        "design-spec": "focused",
        "requirements-spec": "baseline",
        "interface-spec": "baseline",
        "test-report": "baseline",
        "user-manual": "baseline",
        "operations-manual": "baseline",
    }


@pytest.mark.parametrize(
    ("user_request", "skill", "mode"),
    [
        ("请写一份技术报告", "oh-my-technology", "technical-report"),
        ("请制作系统设计说明", "oh-my-technology", "design-spec"),
        ("只调整 Word 页眉和页码", "word-document", "docx-layout"),
        ("检查发明专利权利要求", "oh-my-patent", None),
    ],
)
def test_route_selects_implemented_skill(user_request, skill, mode):
    result = route(user_request, ROOT)
    assert result["selected"] == skill
    assert result["matches"][0]["status"] == "implemented"
    assert result["matches"][0]["mode"] == mode
    assert not result["needs_clarification"]


def test_route_selects_proposal_preparation():
    result = route("请准备项目申报书和预算说明", ROOT)
    assert result["selected"] == "oh-my-proposal"
    assert not result["needs_clarification"]
    assert result["matches"][0]["status"] == "implemented"


def test_route_keeps_ambiguous_composition_explicit():
    result = route("把专利技术内容整理成技术报告并排版成 Word", ROOT)
    assert result["selected"] == "word-skills"
    assert not result["needs_clarification"]
    assert {item["skill"] for item in result["matches"]} == {"oh-my-patent", "word-document", "oh-my-technology"}


def test_route_selects_interface_mode():
    result = route("请写一份接口说明", ROOT)
    assert result["selected"] == "oh-my-technology"
    assert result["matches"][0]["mode"] == "interface-spec"
    assert result["matches"][0]["mode_scope"] == "baseline"
    assert result["matches"][0]["status"] == "implemented"
    assert not result["needs_clarification"]


def test_contract_dataclasses_are_versioned_and_json_ready():
    values = [
        CaseManifest("case-1", "technical-document", "technical-report"),
        Source("S1", "sources/S1.txt", "a" * 64),
        Fact("F1", "已核对的事实", ["S1"], ["L1"], "verified"),
    ]
    for value in values:
        result = to_dict(value)
        assert result["schema_version"] == 1
        json.dumps(result, ensure_ascii=False)


def test_v1_contract_rejects_malformed_nested_values():
    with pytest.raises(ValueError, match="schema_version=1"):
        validate_draft_v1({"schema_version": 2, "mode": "technical-report", "title": "x", "sections": []})
    with pytest.raises(ValueError, match="claim_ids"):
        validate_draft_v1({
            "schema_version": 1,
            "mode": "technical-report",
            "title": "x",
            "sections": [{"id": "s", "title": "S", "blocks": [{"claim_ids": [1]}]}],
        })


def test_list_skills_is_registry_backed():
    names = {row["name"] for row in list_skills(ROOT)}
    assert "word-skills" in names
    assert "oh-my-proposal" in names
    technology = next(row for row in list_skills(ROOT) if row["name"] == "oh-my-technology")
    assert technology["mode_scope"]["technical-report"] == "focused"


def test_text_writing_routes_keep_production_optional():
    for request, skill, optional in [
        ("请写一份技术报告", "oh-my-technology", ["word-document"]),
        ("请准备软著材料", "oh-my-copyright", ["word-document"]),
        ("审阅专利权利要求", "oh-my-patent", []),
    ]:
        result = route(request, ROOT)
        assert result["selected"] == skill
        assert not result["needs_clarification"]
        assert result["matches"][0]["dependencies"] == []
        assert result["matches"][0]["optional_dependencies"] == optional
        assert "未执行" in result["reason"]


def _dependency_registry(root, writer):
    (root / "registry").mkdir(exist_ok=True)
    path = root / "registry/skills.yaml"
    path.write_text(yaml.safe_dump({"schema_version": 1, "skills": [
        {"name": "writer", "kind": "business", "status": "planned", "modes": ["draft"], **writer},
        {"name": "renderer", "kind": "production", "status": "planned", "modes": ["docx"]},
    ]}), encoding="utf-8")


def test_legacy_registry_and_optional_dependency_listing(tmp_path):
    _dependency_registry(tmp_path, {"dependencies": ["renderer"]})
    legacy = list_skills(tmp_path)[0]
    assert legacy["dependencies"] == ["renderer"]
    assert legacy["optional_dependencies"] == []
    _dependency_registry(tmp_path, {"optional_dependencies": ["renderer"]})
    current = list_skills(tmp_path)[0]
    assert current["dependencies"] == []
    assert current["optional_dependencies"] == ["renderer"]


@pytest.mark.parametrize("field", ["dependencies", "optional_dependencies"])
@pytest.mark.parametrize("value, message", [
    ("renderer", "string list"),
    ([1], "string list"),
    (["writer"], "itself"),
    (["renderer", "renderer"], "duplicate"),
    (["missing"], "unknown"),
])
def test_invalid_dependency_declarations_are_rejected(tmp_path, field, value, message):
    _dependency_registry(tmp_path, {field: value})
    with pytest.raises(ValueError, match=message):
        load_registry(tmp_path)


def test_required_and_optional_dependencies_cannot_overlap(tmp_path):
    _dependency_registry(tmp_path, {"dependencies": ["renderer"], "optional_dependencies": ["renderer"]})
    with pytest.raises(ValueError, match="overlap"):
        load_registry(tmp_path)


def test_cli_dependency_metadata_and_route_execution_boundary(capsys):
    assert main(["skills", "list", "--json"]) == 0
    listed = json.loads(capsys.readouterr().out)
    technology = next(row for row in listed["skills"] if row["name"] == "oh-my-technology")
    assert technology["dependencies"] == []
    assert technology["optional_dependencies"] == ["word-document"]
    assert main(["route", "请写一份技术报告"]) == 0
    routed = capsys.readouterr().out
    assert "status: matched" in routed
    assert "未执行" in routed
    assert "optional: word-document" in routed
    assert "status: ready" not in routed
