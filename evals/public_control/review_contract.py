"""Mechanical validation for the public writing review contract v3."""
from __future__ import annotations

import json
from typing import Any

DIMENSIONS = (
    "task_coverage", "factual_support", "reasoning_tradeoffs",
    "domain_expression", "reader_usability", "source_localization",
)
SEVERITIES = {"minor", "material"}


def _strings(value: Any):
    """Yield string leaves from already-decoded JSON values."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)


def candidate_quote_text(raw: str) -> list[str]:
    """Return decoded JSON string leaves, falling back to raw text if invalid."""
    try:
        value = json.loads(raw)
    except (ValueError, TypeError):
        return [raw] if raw else []
    return list(_strings(value))


def _nonblank(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and value.strip().lower() not in {
        "n/a", "na", "none", "unknown", "tbd", "source basis", "reason",
    }


def validate_review(value: Any, candidate_ids: list[str], candidate_texts: dict[str, str]) -> dict:
    """Separate minimal JSON contract shape from review/rubric compliance."""
    shape_errors: list[str] = []
    if not isinstance(value, dict):
        return {"structure_valid": False, "rubric_valid": False,
                "errors": ["response must be one JSON object"]}
    assessments = value.get("assessments")
    if not isinstance(assessments, list):
        shape_errors.append("assessments must be a list")
        assessments = []
    for index, item in enumerate(assessments):
        if not isinstance(item, dict):
            shape_errors.append(f"assessment[{index}] must be an object")
            continue
        for key, typ in (("id", str), ("scores", dict), ("issues", list), ("severe_failures", list)):
            if not isinstance(item.get(key), typ):
                shape_errors.append(f"assessment[{index}].{key} has wrong or missing type")
    if not isinstance(value.get("preference_order"), list):
        shape_errors.append("preference_order must be a list")
    if not isinstance(value.get("uncertainties"), list):
        shape_errors.append("uncertainties must be a list")
    if shape_errors:
        return {"structure_valid": False, "rubric_valid": False, "errors": shape_errors}

    errors: list[str] = []
    if not all(isinstance(item, str) for item in value["uncertainties"]):
        errors.append("uncertainties entries must be strings")
    ids = [item["id"] for item in assessments]
    if len(ids) != len(set(ids)):
        errors.append("assessment IDs must be unique")
    if len(candidate_ids) != len(set(candidate_ids)):
        errors.append("frozen candidate IDs are not unique")
    if set(ids) != set(candidate_ids) or len(ids) != len(candidate_ids):
        errors.append("assessments must cover every candidate exactly once")
    by_id = {item["id"]: item for item in assessments}

    for candidate_id, item in by_id.items():
        scores = item["scores"]
        if set(scores) != set(DIMENSIONS):
            errors.append(f"{candidate_id}: scores must contain exactly the six dimensions")
        for dimension, score in scores.items():
            if type(score) is not int or not 0 <= score <= 4:
                errors.append(f"{candidate_id}: {dimension} must be an integer from 0 to 4")
        issues = item["issues"]
        for index, issue in enumerate(issues):
            label = f"{candidate_id}: issue[{index}]"
            if not isinstance(issue, dict):
                errors.append(f"{label} must be an object")
                continue
            if issue.get("dimension") not in DIMENSIONS:
                errors.append(f"{label} has invalid dimension")
            severity = issue.get("severity")
            if not isinstance(severity, str) or severity not in SEVERITIES:
                errors.append(f"{label} has invalid severity")
            if not _nonblank(issue.get("reason")):
                errors.append(f"{label} needs a non-empty reason")
            if not _nonblank(issue.get("source_basis")):
                errors.append(f"{label} needs a non-empty source_basis")
            _check_quote(errors, label, issue.get("output_quote"), candidate_texts.get(candidate_id, ""))
        for dimension, score in scores.items():
            if type(score) is int and 0 <= score < 4 and not any(
                isinstance(issue, dict) and issue.get("dimension") == dimension for issue in issues
            ):
                errors.append(f"{candidate_id}: score below 4 for {dimension} needs a matching issue")
        for index, failure in enumerate(item["severe_failures"]):
            label = f"{candidate_id}: severe_failures[{index}]"
            if not isinstance(failure, dict):
                errors.append(f"{label} must be an object")
                continue
            if not _nonblank(failure.get("reason")):
                errors.append(f"{label} needs a non-empty reason")
            if not _nonblank(failure.get("source_basis")):
                errors.append(f"{label} needs a non-empty source_basis")
            _check_quote(errors, label, failure.get("output_quote"), candidate_texts.get(candidate_id, ""))

    order = value["preference_order"]
    if (not all(isinstance(x, str) for x in order) or len(order) != len(set(order))
            or len(order) != len(candidate_ids) or set(order) != set(candidate_ids)):
        errors.append("preference_order must contain every candidate ID exactly once")
    return {"structure_valid": True, "rubric_valid": not errors, "errors": errors}


def _check_quote(errors: list[str], label: str, quote: Any, candidate_raw: str) -> None:
    if not isinstance(quote, str) or not quote.strip():
        errors.append(f"{label} needs an exact output_quote")
        return
    if not any(quote in leaf for leaf in candidate_quote_text(candidate_raw)):
        errors.append(f"{label} output_quote is not an exact substring of a candidate JSON string leaf")
