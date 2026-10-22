import json
import sys
from pathlib import Path

import pytest

from evals.public_control.review_contract import DIMENSIONS, validate_review

sys.path.insert(0, str(Path(__file__).resolve().parent))
import judge_v3


IDS = ["D1", "D2"]
CANDIDATES = {
    "D1": json.dumps({"draft": {"sections": [{"text": "设备按每分钟12转运行。"}]}}, ensure_ascii=False),
    "D2": json.dumps({"draft": {"sections": [{"text": "设备按每分钟10转运行。"}]}}, ensure_ascii=False),
}


def valid_review():
    return {
        "assessments": [
            {"id": "D1", "scores": {dimension: 4 for dimension in DIMENSIONS}, "issues": [], "severe_failures": []},
            {"id": "D2", "scores": {dimension: 4 for dimension in DIMENSIONS}, "issues": [], "severe_failures": []},
        ],
        "preference_order": ["D1", "D2"], "uncertainties": [],
    }


def test_valid_review_and_json_escaped_quote_are_accepted():
    candidates = {"D1": json.dumps({"draft": "设备称：\"正常\"。"}, ensure_ascii=False), "D2": CANDIDATES["D2"]}
    result = valid_review()
    result["assessments"][0]["scores"]["factual_support"] = 3
    result["assessments"][0]["issues"] = [{
        "dimension": "factual_support", "output_quote": '设备称："正常"。',
        "source_basis": "materials/manual.txt 第2节未记载此结论", "severity": "material",
        "reason": "该结论缺少材料依据",
    }]
    checked = validate_review(result, IDS, candidates)
    assert checked["structure_valid"] is True
    assert checked["rubric_valid"] is True


def test_missing_candidate_is_rejected():
    result = valid_review()
    result["assessments"].pop()
    checked = validate_review(result, IDS, CANDIDATES)
    assert checked["structure_valid"] is True
    assert checked["rubric_valid"] is False
    assert any("cover every candidate" in error for error in checked["errors"])


def test_duplicate_assessment_id_is_rejected():
    result = valid_review()
    result["assessments"][1]["id"] = "D1"
    result["preference_order"] = ["D1", "D2"]
    checked = validate_review(result, IDS, CANDIDATES)
    assert checked["rubric_valid"] is False
    assert any("IDs must be unique" in error for error in checked["errors"])


def test_low_score_without_dimension_issue_is_rejected():
    result = valid_review()
    result["assessments"][0]["scores"]["task_coverage"] = 2
    checked = validate_review(result, IDS, CANDIDATES)
    assert checked["rubric_valid"] is False
    assert any("needs a matching issue" in error for error in checked["errors"])


def test_nonexistent_quote_is_rejected():
    result = valid_review()
    result["assessments"][0]["scores"]["factual_support"] = 3
    result["assessments"][0]["issues"] = [{
        "dimension": "factual_support", "output_quote": "不存在于候选中的文字",
        "source_basis": "materials/manual.txt 第2节", "severity": "minor", "reason": "缺少支持",
    }]
    checked = validate_review(result, IDS, CANDIDATES)
    assert checked["rubric_valid"] is False
    assert any("not an exact substring" in error for error in checked["errors"])


def test_empty_source_basis_is_rejected():
    result = valid_review()
    result["assessments"][0]["scores"]["factual_support"] = 3
    result["assessments"][0]["issues"] = [{
        "dimension": "factual_support", "output_quote": "设备按每分钟12转运行。",
        "source_basis": "  ", "severity": "minor", "reason": "缺少支持",
    }]
    checked = validate_review(result, IDS, CANDIDATES)
    assert checked["rubric_valid"] is False
    assert any("non-empty source_basis" in error for error in checked["errors"])


def test_incomplete_preference_order_is_rejected():
    result = valid_review()
    result["preference_order"] = ["D1"]
    checked = validate_review(result, IDS, CANDIDATES)
    assert checked["rubric_valid"] is False
    assert any("preference_order" in error for error in checked["errors"])


def test_structure_and_rubric_validity_are_distinct():
    result = valid_review()
    result["assessments"][0]["scores"]["task_coverage"] = 5
    checked = validate_review(result, IDS, CANDIDATES)
    assert checked["structure_valid"] is True
    assert checked["rubric_valid"] is False


def test_malformed_severity_and_whitespace_quote_are_rejected_without_crashing():
    result = valid_review()
    result["assessments"][0]["scores"]["factual_support"] = 3
    result["assessments"][0]["issues"] = [{
        "dimension": "factual_support", "output_quote": "   ", "source_basis": "材料未说明",
        "severity": ["material"], "reason": "缺少材料支持",
    }]
    checked = validate_review(result, IDS, CANDIDATES)
    assert checked["rubric_valid"] is False
    assert any("invalid severity" in error for error in checked["errors"])
    assert any("exact output_quote" in error for error in checked["errors"])


def test_uncertainties_must_be_strings():
    result = valid_review()
    result["uncertainties"] = [{"note": "uncertain"}]
    checked = validate_review(result, IDS, CANDIDATES)
    assert checked["rubric_valid"] is False
    assert any("uncertainties entries must be strings" in error for error in checked["errors"])


def _write_frozen_review(root: Path, orientation: int, score_d1: int):
    job_id = f"case--r01--o{orientation}"
    folder = root / "jobs" / job_id
    folder.mkdir(parents=True)
    candidates = {"D1": CANDIDATES["D1"], "D2": CANDIDATES["D2"]}
    prompt = "frozen\n\nTASK AND DATA:\n" + json.dumps({"candidates": candidates}, ensure_ascii=False)
    (folder / "prompt.txt").write_text(prompt, encoding="utf-8")
    result = valid_review()
    if score_d1 < 4:
        result["assessments"][0]["scores"]["task_coverage"] = score_d1
        result["assessments"][0]["issues"] = [{
            "dimension": "task_coverage", "output_quote": "设备按每分钟12转运行。",
            "source_basis": "任务要求说明操作步骤，候选遗漏了步骤", "severity": "material",
            "reason": "请求的步骤没有覆盖",
        }]
    response_path = folder / "response.txt"
    response_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    job = {"job_id": job_id, "candidate_ids": IDS, "prompt_sha256": judge_v3.base.sha(folder / "prompt.txt")}
    cached_result = {
        "job_id": job_id, "requested_model": "gpt-6-luna", "return_code": 0, "timed_out": False,
        "turn_completed": True, "turn_failed": False, "prompt_sha256": job["prompt_sha256"],
        "response_sha256": judge_v3.base.sha(response_path),
        # Deliberately false to prove summary recomputes validation from the response.
        "structure_valid": False, "rubric_valid": False,
    }
    return job, cached_result


def test_summary_uses_only_o0_and_recomputes_validity(tmp_path):
    identity = {}
    jobs, results = [], []
    for orientation, low_score in ((0, 4), (1, 0)):
        job, result = _write_frozen_review(tmp_path, orientation, low_score)
        jobs.append(job)
        results.append(result)
        identity[job["job_id"]] = {"D1": {"condition": "plain"}, "D2": {"condition": "current"}}
    identity_path = tmp_path / "identity-map.json"
    identity_path.write_text(json.dumps(identity), encoding="utf-8")
    frozen = {"identity_map_sha256": judge_v3.base.sha(identity_path), "jobs": jobs}
    freeze_path = tmp_path / "freeze.json"
    freeze_path.write_text(json.dumps(frozen), encoding="utf-8")
    (tmp_path / "freeze.sha256").write_text(judge_v3.base.sha(freeze_path) + "  freeze.json\n", encoding="ascii")

    summary = judge_v3.summarize(tmp_path, results)
    assert summary["primary_orientation"] == "o0"
    assert summary["primary_validated_jobs"] == 1
    assert summary["all_orientations_validated_jobs"] == 2
    assert summary["condition_summary_from_validated_o0_only"]["plain"]["mean_scores"]["task_coverage"] == 4
    assert summary["orientation_status"]["o1"]["validated_jobs"] == 1
    assert all(row["status"] == "validated" for row in summary["results"])


def test_summary_rejects_response_rewrite(tmp_path):
    job, result = _write_frozen_review(tmp_path, 0, 4)
    identity = {job["job_id"]: {"D1": {"condition": "plain"}, "D2": {"condition": "current"}}}
    identity_path = tmp_path / "identity-map.json"
    identity_path.write_text(json.dumps(identity), encoding="utf-8")
    frozen = {"identity_map_sha256": judge_v3.base.sha(identity_path), "jobs": [job]}
    freeze_path = tmp_path / "freeze.json"
    freeze_path.write_text(json.dumps(frozen), encoding="utf-8")
    (tmp_path / "freeze.sha256").write_text(judge_v3.base.sha(freeze_path) + "  freeze.json\n", encoding="ascii")
    response_path = tmp_path / "jobs" / job["job_id"] / "response.txt"
    response_path.write_text("rewritten", encoding="utf-8")
    with pytest.raises(ValueError, match="response changed"):
        judge_v3.summarize(tmp_path, [result])


def test_cached_result_rejects_response_rewrite(tmp_path):
    job, result = _write_frozen_review(tmp_path, 0, 4)
    folder = tmp_path / "jobs" / job["job_id"]
    (folder / "result.json").write_text(json.dumps(result), encoding="utf-8")
    (folder / "response.txt").write_text("rewritten", encoding="utf-8")
    with pytest.raises(ValueError, match="response changed"):
        judge_v3.run_one(tmp_path, job)
