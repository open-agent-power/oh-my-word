"""Mode-specific checks bound to the text and reviewed evidence of a draft."""
from .common import finding
from .evidence import block_text


RECORDS = {
    "requirements-spec": ("requirements", ("statement", "acceptance")),
    "interface-spec": ("interfaces", ("signature", "request", "response", "errors", "auth", "version")),
    "test-report": ("test_cases", ("expected", "environment")),
    "user-manual": ("steps", ("action", "expected_result")),
    "operations-manual": ("procedures", ("command", "environment", "expected_result", "rollback")),
}


def scaffold(mode):
    if mode in {"technical-report", "design-spec"}:
        return {"task_requirements": [{"id": "T1", "text": "", "acceptance": "", "block_ids": []}]}
    if mode not in RECORDS:
        return {}
    key, fields = RECORDS[mode]
    record = {"id": "replace-me", **{field: "" for field in fields}, "block_ids": [], "claim_ids": []}
    if mode == "test-report":
        record.update(status="not-run", actual="")
    elif mode in {"user-manual", "operations-manual"}:
        record["status"] = "unverified"
    return {key: [record], **({"conclusion": "incomplete"} if mode == "test-report" else {})}


def validate(draft, ledger):
    mode = draft["mode"]
    if mode not in RECORDS:
        return []
    key, fields = RECORDS[mode]
    issues = []
    records = draft.get(key)
    if not isinstance(records, list) or not records:
        return [finding("MODE_RECORDS", f"{mode} requires a nonempty {key} array")]
    blocks = {b.get("id"): b for s in draft["sections"] for b in s["blocks"]}
    verified = {c.get("id") for c in ledger["claims"] if c.get("status") == "verified"}
    seen = set()
    statuses = []
    for record in records:
        if not isinstance(record, dict):
            issues.append(finding("MODE_RECORD", f"{key} entries must be objects"))
            continue
        rid = record.get("id")
        if not isinstance(rid, str) or not rid.strip() or rid in seen:
            issues.append(finding("MODE_ID", "mode records require unique nonempty ids"))
        else:
            seen.add(rid)
        refs = record.get("block_ids")
        if not isinstance(refs, list) or not refs or any(not isinstance(r, str) or r not in blocks for r in refs):
            issues.append(finding("MODE_TRACE", f"{rid}: block_ids must reference rendered content"))
            text = ""
        else:
            text = "\n".join(block_text(blocks[r]) for r in refs)
        required = list(fields)
        if mode == "test-report":
            status = record.get("status")
            statuses.append(status)
            if status not in ("passed", "failed", "blocked", "not-run"):
                issues.append(finding("TEST_STATUS", f"{rid}: invalid execution status"))
            if status in ("passed", "failed"):
                required.append("actual")
            elif record.get("actual"):
                issues.append(finding("TEST_NOT_EXECUTED", f"{rid}: unexecuted tests cannot contain actual results"))
            # The execution status must be visible; metadata alone cannot hide failures.
            if not isinstance(status, str) or status not in text:
                issues.append(finding("TEST_VISIBLE_STATUS", f"{rid}: show the execution status in the report"))
        if mode in ("user-manual", "operations-manual") and record.get("status") != "verified":
            issues.append(finding("PROCEDURE_UNVERIFIED", f"{rid}: record a real operation before delivery"))
        for field in required:
            content = record.get(field)
            if not isinstance(content, str) or not content.strip():
                issues.append(finding("MODE_FIELD", f"{rid}: {field} is required"))
            elif content not in text:
                issues.append(finding("MODE_CONTENT", f"{rid}: {field} must appear in referenced blocks"))
        claims = record.get("claim_ids")
        needs_evidence = mode != "test-report" or record.get("status") in ("passed", "failed")
        if not isinstance(claims, list) or any(not isinstance(c, str) or c not in verified for c in claims) or (needs_evidence and not claims):
            issues.append(finding("MODE_EVIDENCE", f"{rid}: verified claim_ids are required"))
        elif isinstance(refs, list) and all(isinstance(r, str) and r in blocks for r in refs):
            rendered_claims = {c for r in refs for c in blocks[r].get("claim_ids", [])}
            if set(claims) - rendered_claims:
                issues.append(finding("MODE_EVIDENCE", f"{rid}: claims must be linked from rendered blocks"))
    if mode == "test-report":
        conclusion = draft.get("conclusion")
        if conclusion not in ("passed", "failed", "incomplete"):
            issues.append(finding("TEST_CONCLUSION", "conclusion must be passed/failed/incomplete"))
        elif conclusion == "passed" and any(s != "passed" for s in statuses):
            issues.append(finding("TEST_CONCLUSION", "failed or unexecuted cases cannot yield a passed report"))
        elif conclusion == "failed" and "failed" not in statuses:
            issues.append(finding("TEST_CONCLUSION", "failed conclusion needs a failed case"))
        conclusion_section = next((s for s in draft["sections"] if s["id"] == "conclusion"), {})
        if not isinstance(conclusion, str) or conclusion not in "\n".join(block_text(b) for b in conclusion_section.get("blocks", [])):
            issues.append(finding("TEST_CONCLUSION", "show the overall conclusion in the conclusion section"))
    return issues
