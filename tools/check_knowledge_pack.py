"""Read-only fixed-pack maintenance admission; never certifies current law."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from word_skills.common import sha256  # noqa: E402
from word_skills.knowledge import search, verify_index  # noqa: E402


def audit(index, *, as_of, max_age_days=90, queries=None):
    if isinstance(max_age_days, bool) or not isinstance(max_age_days, int) or max_age_days < 1:
        raise ValueError("max_age_days must be a positive integer")
    checked = verify_index(index)
    retriever = Path(index) / "ragflow.json"
    config_hash = sha256(retriever) if retriever.exists() else None
    rows = []
    for source in checked["documents"]:
        row = {"id": source["id"], "retrieved_at": source["retrieved_at"],
               "revision": source["revision"], "url": source["url"], "status": "invalid-date"}
        try:
            collected = datetime.fromisoformat(source["retrieved_at"].replace("Z", "+00:00")).date()
            age = (as_of - collected).days
            row.update(age_days=age, next_review_due=(collected + timedelta(days=max_age_days)).isoformat(),
                       status="future-date" if age < 0 else "review-due" if age > max_age_days else "within-review-interval")
        except (TypeError, ValueError, AttributeError):
            pass
        rows.append(row)

    cases = []
    if queries is not None:
        if not isinstance(queries, list) or not queries:
            raise ValueError("Query suite must be a nonempty list")
        known, seen = {d["id"] for d in checked["documents"]}, set()
        for item in queries:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"].strip() or item["id"] in seen:
                raise ValueError("Query IDs must be unique nonempty strings")
            seen.add(item["id"])
            if set(item) - {"id", "query", "expected_sources", "top_k", "kind", "topic"}:
                raise ValueError("Unknown query-suite fields")
            expected = item.get("expected_sources")
            if (not isinstance(item.get("query"), str) or not item["query"].strip()
                    or not isinstance(expected, list) or not expected
                    or any(not isinstance(s, str) or s not in known for s in expected)):
                raise ValueError("Queries need nonempty text and expected_sources present in the pack")
            row = {"id": item["id"], "query": item["query"], "expected_sources": expected,
                   "top_k": item.get("top_k", 5), "kind": item.get("kind"), "topic": item.get("topic"), "passed": False}
            try:
                result = search(index, row["query"], row["top_k"], kind=row["kind"], topic=row["topic"])
                if result["kb_id"] != checked["kb_id"]:
                    raise ValueError("Knowledge identity changed during regression")
                found = sorted({hit["source_id"] for hit in result["hits"]})
                missing = sorted(set(expected) - set(found))
                row.update(found_sources=found, missing_sources=missing, passed=not missing)
            except Exception as exc:
                # A selected RAGFlow backend failure is recorded, never switched.
                row["error"] = f"{type(exc).__name__}: {exc}"
            cases.append(row)
    if verify_index(index)["kb_id"] != checked["kb_id"]:
        raise ValueError("Knowledge identity changed during maintenance audit")
    if (sha256(retriever) if retriever.exists() else None) != config_hash:
        raise ValueError("Retrieval configuration changed during maintenance audit")
    passed = bool(rows) and all(r["status"] == "within-review-interval" for r in rows) and bool(cases) and all(r["passed"] for r in cases)
    return {"schema_version": 1, "kb_id": checked["kb_id"], "as_of": as_of.isoformat(),
            "review_interval_days": max_age_days, "integrity": "verified", "sources": rows,
            "backend": "ragflow" if config_hash else "local", "retriever_config_sha256": config_hash,
            "queries": cases, "retrieval_regression": "executed" if queries is not None else "not-executed",
            "status": "pass" if passed else "needs-review", "legal_currency": "not verified",
            "semantic_support": "not automatically evaluated", "active_index_modified": False,
            "limits": "Collection age is a maintenance signal, not proof of validity or applicability. Expected-source recall is not answer correctness. No query suite cannot pass admission."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("index", type=Path)
    parser.add_argument("--as-of", type=date.fromisoformat, required=True, help="Explicit YYYY-MM-DD for repeatable checks")
    parser.add_argument("--max-age-days", type=int, default=90, help="Review interval, not a legal validity period")
    parser.add_argument("--queries", type=Path, help="JSON list of id/query/expected_sources and optional kind/topic/top_k")
    parser.add_argument("--out", type=Path, required=True, help="New report file outside the pack")
    args = parser.parse_args()
    output, index = args.out.resolve(), args.index.resolve()
    if output.exists() or output.is_relative_to(index):
        parser.error("Use a new report path outside the pack; historical reports are preserved")
    report = {"status": "fail", "integrity": "not verified", "legal_currency": "not verified"}
    try:
        queries = json.loads(args.queries.read_text("utf-8")) if args.queries else None
        report = audit(index, as_of=args.as_of, max_age_days=args.max_age_days, queries=queries)
        if args.queries:
            report["query_suite_sha256"] = sha256(args.queries)
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "report": str(output)}, ensure_ascii=False))
    return 0 if report["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
