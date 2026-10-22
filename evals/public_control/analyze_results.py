"""Aggregate public development evaluation runs without expert-quality claims.

The script consumes score.py output for mechanical metrics and optional blind
AI-judge job results. Paired comparisons average repeats within task, then tasks
within project/context, so the project/context is the bootstrap unit.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import re
import hashlib
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from evals.public_control.score import score


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _cluster_values(rows: list[dict], metric: str, condition: str) -> dict[str, float]:
    """Average repeats per task, then tasks within project/context cluster."""
    task_vals: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in rows:
        if row.get("condition") != condition or not isinstance(row.get(metric), (int, float)):
            continue
        task = row.get("task_id", "")
        # task ids are project-prefixed in these development datasets.
        # Each formal task is one paper/context unit. Repeats of that task are
        # averaged here; separate contexts stay separate bootstrap clusters.
        cluster = row.get("cluster_id") or task
        task_vals[(cluster, task)].append(float(row[metric]))
    clusters: dict[str, list[float]] = defaultdict(list)
    for (cluster, _task), vals in task_vals.items():
        clusters[cluster].append(sum(vals) / len(vals))
    return {key: sum(vals) / len(vals) for key, vals in clusters.items()}


def _project_from_task(task: str) -> str:
    if task.startswith("scifact-"):
        return "scifact"
    if task.startswith("cmrc-"):
        return "cmrc"
    for prefix in ("fastapi-", "express-"):
        if task.startswith(prefix):
            return prefix[:-1]
    return task.split("-", 1)[0]


def paired_bootstrap(rows: list[dict], metric: str, left: str, right: str,
                     seed: int = 20261021, draws: int = 10000) -> dict:
    lv = _cluster_values(rows, metric, left)
    rv = _cluster_values(rows, metric, right)
    shared = sorted(lv.keys() & rv.keys())
    diffs = [lv[c] - rv[c] for c in shared]
    if not diffs:
        return {"left": left, "right": right, "metric": metric, "n_clusters": 0,
                "difference_left_minus_right": None, "ci95": None, "clusters": []}
    rng = random.Random(seed)
    samples = [sum(rng.choices(diffs, k=len(diffs))) / len(diffs) for _ in range(draws)]
    samples.sort()
    return {"left": left, "right": right, "metric": metric, "n_clusters": len(diffs),
            "difference_left_minus_right": sum(diffs) / len(diffs),
            "ci95": [samples[int(.025 * draws)], samples[min(draws - 1, int(.975 * draws))]],
            "clusters": [{"cluster": c, "difference": lv[c] - rv[c]} for c in shared],
            "bootstrap_seed": seed, "bootstrap_draws": draws}


def _available_comparisons(rows: list[dict], seed: int) -> list[dict]:
    """Compare only requested condition pairs and metrics present on both sides."""
    result = []
    for metric in ("label_correct", "cmrc_em", "cmrc_f1"):
        present = {r.get("condition") for r in rows
                   if isinstance(r.get(metric), (int, float))}
        for left, right in (("A", "B"), ("B", "C"), ("B", "G")):
            if left in present and right in present:
                result.append(paired_bootstrap(rows, metric, left, right, seed))
    return result


def load_mechanical(run_specs: list[tuple[str, Path]], gold: Path) -> list[dict]:
    rows = []
    for run_name, run_dir in run_specs:
        result = score(run_dir, gold)
        for row in result["rows"]:
            row = dict(row)
            row["run_name"] = run_name
            rows.append(row)
    return rows


def _usage_totals(run_specs: list[tuple[str, Path]]) -> dict:
    fields = ("input_tokens", "cached_input_tokens", "cache_write_input_tokens",
              "output_tokens", "reasoning_output_tokens")
    totals = {f: 0 for f in fields}
    missing = {f: 0 for f in fields}
    seconds_known = 0.0
    seconds_missing = 0
    attempts = 0
    for _name, root in run_specs:
        for path in sorted((root / "attempts").glob("*/attempt-*/run.json")):
            run = _read_json(path)
            if run.get("reused") or run.get("execution_state") == "reused":
                continue
            attempts += 1
            usage = run.get("usage", run.get("token_usage")) or {}
            for field in fields:
                value = usage.get(field)
                if isinstance(value, (int, float)):
                    totals[field] += value
                else:
                    missing[field] += 1
            elapsed = run.get("elapsed_seconds")
            if isinstance(elapsed, (int, float)):
                seconds_known += elapsed
            else:
                seconds_missing += 1
    return {"counted_attempts_including_failures": attempts,
            "token_fields": {f: {"known_subtotal": totals[f], "unknown_attempts": missing[f],
                                 "exact": missing[f] == 0} for f in fields},
            "elapsed_seconds": {"known_subtotal": seconds_known,
                                "unknown_attempts": seconds_missing,
                                "exact": seconds_missing == 0},
            "note": "Input tokens include cached input; cached tokens are reported separately and not added again. Reused attempts excluded."}


def _extract_judge_rows(judge_dir: Path, mechanical: list[dict]) -> tuple[list[dict], dict]:
    identity = _read_json(judge_dir / "identity-map.json")
    response_index = {r.get("response_sha256"): r for r in mechanical if r.get("response_sha256")}
    rows = []
    for result_path in sorted((judge_dir / "jobs").glob("*/result.json")):
        job_id = result_path.parent.name
        try:
            order = int(job_id.rsplit("--o", 1)[1])
        except (IndexError, ValueError):
            order = None
        job_meta = _read_json(result_path)
        schema_valid = job_meta.get("schema_valid") is True
        try:
            payload = json.loads((result_path.parent / "response.txt").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            payload = {}
        mapped_job = identity.get(job_id, {})
        assessments = {a.get("id"): a for a in payload.get("assessments", []) if isinstance(a, dict)}
        blind_to_condition = {blind: candidate.get("condition") for blind, candidate in mapped_job.items()
                              if isinstance(candidate, dict)} if isinstance(mapped_job, dict) else {}
        rank_by_condition = {blind_to_condition.get(blind): rank for rank, blind in
                             enumerate(payload.get("preference_order", [])) if blind_to_condition.get(blind)}
        for blind_id, mapped in mapped_job.items() if isinstance(mapped_job, dict) else []:
            if not isinstance(mapped, dict):
                continue
            response = mapped.get("response")
            if isinstance(response, dict):
                response = json.dumps(response, ensure_ascii=False)
            fingerprint = hashlib.sha256(response.encode("utf-8")).hexdigest() if isinstance(response, str) else None
            assessment = assessments.get(blind_id, {})
            # Invalid judge envelopes can contain a plausible partial subset;
            # preserve their status but never include those partial scores.
            assessment_ok = schema_valid and blind_id in assessments
            scores = assessment.get("scores", {}) if assessment_ok else {}
            issues = assessment.get("issues", []) if assessment_ok else []
            issues = list(issues) + [{"severity": "severe", "reason": x} for x in assessment.get("severe_failures", [])]
            searchable = response or ""
            try:
                decoded = json.loads(response) if response else None
                def strings(value):
                    if isinstance(value, str):
                        yield value
                    elif isinstance(value, list):
                        for child in value:
                            yield from strings(child)
                    elif isinstance(value, dict):
                        for child in value.values():
                            yield from strings(child)
                searchable += "\n" + "\n".join(strings(decoded))
            except ValueError:
                pass
            issue_rows = []
            for item in issues:
                quote = item.get("output_quote", item.get("quote", "")) if isinstance(item, dict) else str(item)
                issue_rows.append({"issue": item, "quote_in_response": bool(quote and quote in searchable)})
            source = response_index.get(fingerprint, {})
            task_id = mapped.get("task_id") or job_id.split("--r", 1)[0]
            rows.append({"job_id": job_id, "orientation": order, "schema_valid": schema_valid,
                         "assessment_present": blind_id in assessments,
                         "judge_source": "AI evaluator; not expert review",
                         "blind_id": blind_id, "task_id": task_id, "condition": mapped.get("condition"),
                         "project": _project_from_task(task_id),
                         "task_kind": "technical-report" if "technical-report" in task_id else "design-spec",
                         "scores": scores,
                         "preference_order": payload.get("preference_order", []),
                         "preference_rank": rank_by_condition.get(mapped.get("condition")) if schema_valid else None,
                         "issues_for_root_review": issue_rows, "response_sha256": fingerprint,
                         "matched_mechanical_response": bool(source)})
    orientation0 = [r for r in rows if r["orientation"] == 0 and r.get("schema_valid")]
    dims: dict[str, list[float]] = defaultdict(list)
    dims_by_kind: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in orientation0:
        for name, value in (row.get("scores") or {}).items():
            if isinstance(value, (int, float)):
                dims[name].append(value)
                dims_by_kind[row["task_kind"]][name].append(value)
    wtl = defaultdict(lambda: {"W": 0, "T": 0, "L": 0})
    ranked_jobs: dict[tuple[str, int], dict[str, int]] = defaultdict(dict)
    for row in rows:
        if row.get("schema_valid") and row.get("preference_rank") is not None:
            ranked_jobs[(row["job_id"], row["orientation"])][row["condition"]] = row["preference_rank"]
    for (job_id, orientation), ranks in ranked_jobs.items():
        if orientation != 0:
            continue
        conditions = sorted(ranks)
        for i, left in enumerate(conditions):
            for right in conditions[i + 1:]:
                if ranks[left] == ranks[right]:
                    wtl[f"{left}_vs_{right}"]["T"] += 1
                else:
                    winner, loser = (left, right) if ranks[left] < ranks[right] else (right, left)
                    wtl[f"{winner}_vs_{loser}"]["W"] += 1
                    wtl[f"{loser}_vs_{winner}"]["L"] += 1
    orientations: dict[tuple[str, int], dict[str, int]] = {}
    for (job_id, orientation), ranks in ranked_jobs.items():
        # Remove the orientation suffix while retaining repeat/task identity.
        base_id = re.sub(r"--o[01]$", "", job_id)
        orientations[(base_id, orientation)] = ranks
    stability = []
    for base_id in sorted({key[0] for key in orientations}):
        ranks1 = orientations.get((base_id, 1))
        if ranks1 is None or (base_id, 0) not in orientations:
            continue
        ranks0 = orientations[(base_id, 0)]
        common = sorted(ranks0.keys() & ranks1.keys())
        concordant = discordant = ties = 0
        for i, a in enumerate(common):
            for b in common[i + 1:]:
                d0, d1 = ranks0[a] - ranks0[b], ranks1[a] - ranks1[b]
                if d0 == 0 or d1 == 0:
                    ties += 1
                elif d0 * d1 > 0:
                    concordant += 1
                else:
                    discordant += 1
        denom = concordant + discordant
        stability.append({"base_job_id": base_id, "shared_conditions": len(common),
                          "pairwise_order_agreement": concordant / denom if denom else None,
                          "kendall_tau_a": (concordant - discordant) / denom if denom else None,
                          "tied_pairs": ties})
    judge_usage = _judge_usage(judge_dir)
    return rows, {"primary_orientation": 0, "secondary_orientation": 1,
                  "dimension_means_orientation0": {k: _mean(v) for k, v in sorted(dims.items())},
                  "dimension_means_orientation0_by_task_kind": {
                      kind: {dim: _mean(vals) for dim, vals in sorted(values.items())}
                      for kind, values in sorted(dims_by_kind.items())},
                  "pairwise_win_tie_loss_orientation0": dict(wtl),
                  "orientation1_vs_orientation0_order_stability": {
                      "paired_jobs": len(stability),
                      "mean_pairwise_order_agreement": _mean([x["pairwise_order_agreement"] for x in stability if x["pairwise_order_agreement"] is not None]),
                      "per_job": stability},
                  "invalid_or_incomplete_jobs": sorted({r["job_id"] for r in rows if not r.get("schema_valid")}),
                  "valid_orientation0_assessments": sum(r.get("orientation") == 0 and r.get("schema_valid") and r.get("assessment_present") for r in rows),
                  "orientation1_purpose": "order-stability only; excluded from primary means",
                  "source_note": "AI-generated judgments are orientation evidence, not expert ratings or verified allegations. Do not use AI ranking to establish method superiority.",
                  "limitations": [
                      "The evaluator checklist included a design-recommendations criterion; this was not required by the technical-report task, so report reasoning_tradeoffs scores are exploratory diagnostics and should not drive adoption or a report total.",
                      "Some evaluator comments treated explicitly labeled proposals as factual-support risks; this is a subjective evaluator judgment, not a verified factual error.",
                      "Severe allegations and all issue quotes remain pending root review; quote matching only checks whether the quoted text appears in the response.",
                      "An invalid or incomplete orientation-0 assessment remains missing; orientation 1 is not substituted."
                  ], "judge_usage": judge_usage}


def _judge_usage(judge_dir: Path) -> dict:
    fields = ("input_tokens", "cached_input_tokens", "cache_write_input_tokens",
              "output_tokens", "reasoning_output_tokens")
    totals = {key: 0 for key in fields}
    missing = {key: 0 for key in fields}
    elapsed_known = 0.0
    elapsed_missing = 0
    jobs = 0
    for path in sorted((judge_dir / "jobs").glob("*/result.json")):
        result = _read_json(path)
        jobs += 1
        usage = result.get("usage") or {}
        for key in fields:
            value = usage.get(key)
            if isinstance(value, (int, float)):
                totals[key] += value
            else:
                missing[key] += 1
        elapsed = result.get("elapsed_seconds")
        if isinstance(elapsed, (int, float)):
            elapsed_known += elapsed
        else:
            elapsed_missing += 1
    return {"jobs": jobs, "token_fields": {k: {"known_subtotal": totals[k],
              "unknown_jobs": missing[k], "exact": missing[k] == 0} for k in fields},
            "elapsed_seconds": {"known_subtotal": elapsed_known,
              "unknown_jobs": elapsed_missing, "exact": elapsed_missing == 0},
            "note": "Judge inference usage reported separately from generator usage; input includes cached input, which is not added again."}


def _judge_limitations(scope: str) -> list[str]:
    common = [
        "AI-generated judgments are orientation evidence, not expert ratings; allegations require manual verification against the response, task requirements, and source materials.",
        "Issue-quote matching checks literal text presence only and does not establish whether an allegation is correct.",
        "Orientation 0 is primary. Orientation 1 is used only for order stability; invalid or incomplete assessments are not replaced by the reversed-order result."
    ]
    if scope == "development":
        return common + [
            "The development evaluator checklist included a design-recommendations criterion not required by technical-report tasks; report reasoning_tradeoffs scores are exploratory only and must not drive adoption or a report total.",
            "Some development comments treated explicitly labeled proposals as factual-support risks; this is a subjective evaluator judgment, not a verified factual error."
        ]
    return common + [
        "Heldout-v2 scores and preference rankings remain AI-evaluator judgments; this analysis does not treat them as expert quality findings or proof of method superiority.",
        "Root review of the four repeat-1 orientation-0 groups found a reader_usability penalty for JSON wrapping even though all candidates shared the JSON contract; this is a measurement mismatch.",
        "The rubric required issue evidence for scores below 4, but root review found a D3 reader_usability score of 3 without a corresponding issue and a D1 reasoning_tradeoffs score of 3 without one.",
        "Root review found explicitly labeled proposals treated as factual-support gaps for Gin design-spec G and Flask design-spec B; these evaluator judgments do not establish factual errors."
    ]


def analyze(run_specs: list[tuple[str, Path]], gold: Path, judge_dir: Path | None = None,
            seed: int = 20261021, scope: str = "development") -> dict:
    if scope not in {"development", "heldout"}:
        raise ValueError("scope must be 'development' or 'heldout'")
    rows = load_mechanical(run_specs, gold)
    by_condition = defaultdict(list)
    for row in rows:
        by_condition[row["condition"]].append(row)
    comparisons = _available_comparisons(rows, seed)
    judge_rows, judge_summary = _extract_judge_rows(judge_dir, rows) if judge_dir else ([], None)
    if judge_summary is not None:
        judge_summary["limitations"] = _judge_limitations(scope)
    return {"scope": scope,
            "scope_note": ("Development results are exploratory; no overall significance claim."
                           if scope == "development" else
                           "Heldout scope label; interpretation must follow the pre-registered protocol."),
            "runs": [{"name": name, "path": str(path)} for name, path in run_specs],
            "mechanical_rows": rows,
            "condition_summary": {condition: _summarize(group) for condition, group in sorted(by_condition.items())},
            "paired_exploratory_comparisons": comparisons,
            "usage": _usage_totals(run_specs),
            "ai_judge_summary": judge_summary,
            "ai_judge_rows": judge_rows}


def _summarize(rows: list[dict]) -> dict:
    qa = [r for r in rows if r.get("label_correct") is not None]
    cmrc = [r for r in rows if r.get("cmrc_em") is not None]
    writing = [r for r in rows if r.get("kind") not in {"factual-qa", "qa"}]
    return {"observations": len(rows), "json_objects": sum(bool(r["json_object"]) for r in rows),
            "shared_schema_pass": sum(bool(r["shared_schema_pass"]) for r in rows),
            "writing_observations": len(writing),
            "writing_json_rate": _mean([float(r["json_object"]) for r in writing]),
            "writing_schema_rate": _mean([float(r["shared_schema_pass"]) for r in writing]),
            "qa_accuracy": _mean([float(r["label_correct"]) for r in qa]),
            "qa_macro_f1_present_labels": _macro_f1(qa),
            "qa_n": len(qa), "cmrc_em": _mean([r["cmrc_em"] for r in cmrc]),
            "cmrc_lcs_f1_compat": _mean([r["cmrc_f1"] for r in cmrc]), "cmrc_n": len(cmrc)}


def _macro_f1(rows: list[dict]) -> float | None:
    labels = sorted({r.get("expected_label") for r in rows if r.get("expected_label")})
    if not labels:
        return None
    scores = []
    for label in labels:
        tp = sum(r.get("expected_label") == label and r.get("predicted_label") == label for r in rows)
        fp = sum(r.get("expected_label") != label and r.get("predicted_label") == label for r in rows)
        fn = sum(r.get("expected_label") == label and r.get("predicted_label") != label for r in rows)
        scores.append(2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0)
    return sum(scores) / len(scores)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="append", required=True, metavar="NAME=PATH")
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--judge-dir", type=Path)
    parser.add_argument("--seed", type=int, default=20261021)
    parser.add_argument("--scope", choices=("development", "heldout"), default="development")
    args = parser.parse_args()
    specs = []
    for spec in args.run:
        name, sep, path = spec.partition("=")
        if not sep:
            parser.error(f"invalid --run {spec!r}; expected NAME=PATH")
        specs.append((name, Path(path)))
    result = analyze(specs, args.gold, args.judge_dir, args.seed, args.scope)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "analysis.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if result["mechanical_rows"]:
        with (args.out / "metrics.csv").open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(result["mechanical_rows"][0]))
            writer.writeheader()
            writer.writerows(result["mechanical_rows"])
    if result["ai_judge_rows"]:
        (args.out / "ai_judge_rows.json").write_text(json.dumps(result["ai_judge_rows"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["condition_summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
