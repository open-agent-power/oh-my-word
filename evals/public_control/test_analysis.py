from pathlib import Path

from evals.public_control import analyze_results
from evals.public_control.analyze_results import _judge_limitations, _macro_f1, paired_bootstrap


def test_paired_bootstrap_aggregates_repeats_then_clusters_tasks():
    rows = [
        {"condition": "A", "task_id": "fastapi-x", "metric": 1},
        {"condition": "A", "task_id": "fastapi-x", "metric": 0},
        {"condition": "B", "task_id": "fastapi-x", "metric": 0},
        {"condition": "A", "task_id": "fastapi-y", "metric": 1},
        {"condition": "B", "task_id": "fastapi-y", "metric": 1},
        {"condition": "A", "task_id": "express-z", "metric": 1},
        {"condition": "B", "task_id": "express-z", "metric": 0},
    ]
    result = paired_bootstrap(rows, "metric", "A", "B", seed=11, draws=1000)
    # Repeats within fastapi-x are averaged first; each task/context is one
    # paired unit: (0.5 - 0 + 1 - 1 + 1 - 0) / 3.
    assert result["n_clusters"] == 3
    assert abs(result["difference_left_minus_right"] - 0.5) < 1e-12
    assert result["ci95"][0] <= result["difference_left_minus_right"] <= result["ci95"][1]


def test_macro_f1_uses_only_labels_present_in_gold():
    rows = [
        {"expected_label": "SUPPORT", "predicted_label": "SUPPORT"},
        {"expected_label": "CONTRADICT", "predicted_label": None},
    ]
    assert _macro_f1(rows) == 0.5
    assert _macro_f1([]) is None


def test_b_g_pair_uses_available_metric_and_heldout_scope_label(monkeypatch):
    rows = [
        {"condition": "B", "task_id": "scifact-x", "label_correct": 1},
        {"condition": "B", "task_id": "scifact-x", "label_correct": 0},
        {"condition": "G", "task_id": "scifact-x", "label_correct": 1},
        {"condition": "B", "task_id": "scifact-y", "label_correct": 0},
        {"condition": "G", "task_id": "scifact-y", "label_correct": 1},
    ]
    for row in rows:
        row.update({"json_object": False, "shared_schema_pass": False,
                    "kind": "factual-qa", "cmrc_em": None, "cmrc_f1": None})
    monkeypatch.setattr(analyze_results, "load_mechanical", lambda _runs, _gold: rows)

    result = analyze_results.analyze([], Path("unused-gold.jsonl"), seed=7, scope="heldout")

    comparisons = result["paired_exploratory_comparisons"]
    assert len(comparisons) == 1
    assert comparisons[0]["left"] == "B"
    assert comparisons[0]["right"] == "G"
    assert comparisons[0]["n_clusters"] == 2
    assert comparisons[0]["difference_left_minus_right"] == -0.75
    assert result["scope"] == "heldout"
    assert "Heldout scope label" in result["scope_note"]


def test_judge_limitations_are_scope_specific():
    development = " ".join(_judge_limitations("development"))
    heldout = " ".join(_judge_limitations("heldout"))

    assert "design-recommendations criterion" in development
    assert "design-recommendations criterion" not in heldout
    assert "Some development comments treated explicitly labeled proposals" in development
    assert "Some development comments treated explicitly labeled proposals" not in heldout
    assert "AI-evaluator judgments" in heldout
    assert "JSON wrapping" in heldout
    assert "JSON wrapping" not in development
