"""Recorded task and semantic review, not automatic proof of meaning."""
from .common import finding

FOCUSED = {"technical-report", "design-spec"}


def task_issues(draft):
    records = draft.get("task_requirements")
    if "task_requirements" not in draft:
        return [finding("TASK_COVERAGE_MISSING", "Add task_requirements before final review; legacy drafts remain buildable", "warning")] if draft["mode"] in FOCUSED else []
    if not isinstance(records, list) or not records:
        return [finding("TASK_REQUIREMENTS", "task_requirements must be a nonempty array")]
    blocks = {b["id"] for s in draft["sections"] for b in s["blocks"]}
    issues, seen = [], set()
    for record in records:
        if not isinstance(record, dict):
            issues.append(finding("TASK_REQUIREMENT", "Each task requirement must be an object"))
            continue
        rid = record.get("id")
        if not isinstance(rid, str) or not rid.strip() or rid in seen:
            issues.append(finding("TASK_ID", "Task IDs must be unique nonempty strings"))
        else:
            seen.add(rid)
        for field in ("text", "acceptance"):
            if not isinstance(record.get(field), str) or not record[field].strip():
                issues.append(finding("TASK_FIELD", f"{rid}: {field} required"))
        refs = record.get("block_ids")
        if not isinstance(refs, list) or not refs or any(not isinstance(b, str) or b not in blocks for b in refs):
            issues.append(finding("TASK_TRACE", f"{rid}: reference existing body blocks, including visible gaps"))
    return issues


def review_rows(draft):
    return {
        "task_coverage": [{"id": r["id"], "status": "pending", "notes": ""} for r in draft.get("task_requirements", [])],
        "semantic_support": [{"block_id": b["id"], "status": "pending", "notes": ""}
                             for s in draft["sections"] for b in s["blocks"] if b.get("intent") == "fact"],
    }


def validate_review(draft, report):
    """Require explicit judgments bound to each item; never infer them."""
    if task_issues(draft):
        raise ValueError("Task requirements must be complete and traced before final review")
    expected = review_rows(draft)
    for key, identity, passing in (("task_coverage", "id", {"covered", "not-applicable"}),
                                   ("semantic_support", "block_id", {"supported"})):
        rows = report.get(key)
        ids = {r[identity] for r in expected[key]}
        if not isinstance(rows, list) or len(rows) != len(ids) or any(not isinstance(r, dict) for r in rows):
            raise ValueError(f"{key}: review every item exactly once")
        actual = [r.get(identity) for r in rows]
        if any(not isinstance(i, str) for i in actual) or set(actual) != ids:
            raise ValueError(f"{key}: review every item exactly once")
        if any(r.get("status") not in passing or not isinstance(r.get("notes"), str) or not r["notes"].strip() for r in rows):
            raise ValueError(f"{key}: unresolved coverage or semantic support; record concrete observations")
