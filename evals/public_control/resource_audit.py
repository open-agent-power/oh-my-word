"""Inventory inference records, including failed and invalidated experiments.

This is an accounting lower bound, not a price estimator. Cached input is a
subset of input and is never added to it. Missing usage remains unknown.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


FIELDS = ("input_tokens", "cached_input_tokens", "output_tokens")


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def summarize(records: list[dict]) -> dict:
    return {
        "recorded_attempts": len(records),
        "tokens": {
            key: {
                "known_subtotal": sum(r["usage"].get(key, 0) for r in records
                                      if isinstance(r["usage"].get(key), int)),
                "unknown_attempts": sum(not isinstance(r["usage"].get(key), int)
                                        for r in records),
            } for key in FIELDS
        },
        "aggregate_elapsed_seconds_known": round(sum(r.get("seconds") or 0 for r in records), 3),
        "note": "Aggregate elapsed is sum of attempts, not concurrent wall-clock duration.",
    }


def audit(root: Path) -> dict:
    records = []
    for path in sorted((root / "runs").rglob("run.json")):
        value = read(path)
        run = path.relative_to(root / "runs").parts[0]
        records.append({
            "path": str(path), "category": "generation:" + run,
            "invalidated": (root / "runs" / run / "INVALIDATED.json").exists(),
            "reused": bool(value.get("reused")),
            "generation_observed": value.get("generation_observed"),
            "usage": value.get("usage") or {},
            "seconds": value.get("elapsed_seconds"),
            "record_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })
    for path in sorted((root / "control").rglob("result.json")):
        value = read(path)
        if value.get("requested_model") != "gpt-6-luna":
            continue
        group = path.relative_to(root / "control").parts[0]
        usage = value.get("usage")
        usage_source = "metadata"
        if usage is None and path.with_name("trace.jsonl").is_file():
            events = []
            for line in path.with_name("trace.jsonl").read_text(encoding="utf-8").splitlines():
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "turn.completed":
                    events.append(event)
            if events:
                usage = events[-1].get("usage")
                usage_source = "last turn.completed in preserved trace"
        records.append({
            "path": str(path), "category": "control:" + group,
            "usage": usage or {}, "usage_source": usage_source,
            "seconds": value.get("elapsed_seconds", value.get("seconds")),
            "record_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })
    groups = defaultdict(list)
    for record in records:
        groups[record["category"]].append(record)
    return {
        "snapshot_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "All preserved inference metadata including failures and invalidated v4; excludes unknown in-flight usage.",
        "total": summarize(records),
        "groups": {name: summarize(rows) for name, rows in sorted(groups.items())},
        "known_unrecorded_attempts": [{"run": "formal-v1-dev-ab-v4", "count": 3,
            "reason": "Stopped in-flight when protocol error discovered; usage unknown, not zero."}],
        "limitations": ["No monetary conversion without verified billing prices.",
            "Only controlled CLI inference records are counted; coordinator and worker chat usage is unavailable and excluded.",
            "No operating-system isolation or exact resolved model claim.",
            "Snapshot during active runs is incomplete; refresh after all inference completes.",
            "Never sum cached input into input again."],
        "records": records,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["total"], indent=2))


if __name__ == "__main__":
    main()
