"""Offline schedule, resume and accounting tests; never invokes a model."""
from __future__ import annotations

import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

import formal_runner as formal
import run_public_eval as base


class FormalRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.data = self.root / "data"
        self.data.mkdir()
        material = self.data / "evidence.txt"
        material.write_text("Synthetic offline fixture: the example accepts typed input.", encoding="utf-8")
        tasks = [{"id": name, "kind": kind, "split": "development",
                  "request": "Describe the supplied synthetic fixture.",
                  "materials": [{"path": "evidence.txt", "sha256": base.sha(material), "source_id": "S1"}]}
                 for name, kind in [("scifact-0009-train-dev", "factual-qa"),
                                    ("fastapi-technical-report-dev", "technical-report"),
                                    *[(f"fixture-{i:02}", "factual-qa") for i in range(14)]]]
        self.tasks = self.data / "tasks.jsonl"
        self.tasks.write_text("".join(json.dumps(t) + "\n" for t in tasks), encoding="utf-8")
        prototype_tasks = self.data / "prototypes.jsonl"
        prototype_tasks.write_text("".join(json.dumps(t) + "\n" for t in tasks[:2]), encoding="utf-8")
        self.pilot = base.prepare(Namespace(tasks=prototype_tasks, data_root=self.data,
                                            runs=self.root / "pilots", run_id="fixture-pilot", timeout=10))

    def tearDown(self):
        self.temp.cleanup()

    def prepare(self, name="formal", **kwargs):
        args = Namespace(pilot_run=self.pilot, tasks=self.tasks, data_root=self.data,
                         out=self.root / name, repeat=kwargs.pop("repeat", 3), seed=23,
                         split=kwargs.pop("split", ["development"]), task=kwargs.pop("task", None),
                         condition=kwargs.pop("condition", None), conditions_config=None,
                         context_root=None, reuse_from=None)
        return formal.prepare(args)

    def test_seed_filters_and_repeat_schedule_are_frozen(self):
        run_a = self.prepare("a", task=["scifact-0009-train-dev"], condition=["A"])
        run_b = self.prepare("b", task=["scifact-0009-train-dev"], condition=["A"])
        rows = formal.read_jsonl(run_a / "schedule.jsonl")
        self.assertEqual(len(rows), 3)
        self.assertEqual((run_a / "schedule.jsonl").read_bytes(), (run_b / "schedule.jsonl").read_bytes())
        self.assertTrue(all(r["split"] == "development" and r["condition"] == "A" for r in rows))
        self.assertTrue(formal.verify_formal(run_a)["evaluation_scope"] == "context_only_generation")

    def test_full_development_ab_is_96_jobs_and_reuses_only_matching_b_repeat_one(self):
        root = self.prepare("full-dev")
        rows = formal.read_jsonl(root / "schedule.jsonl")
        self.assertEqual(len(rows), 16 * 2 * 3)
        reuse = [row for row in rows if row.get("reuse_from")]
        self.assertTrue(all(row["condition"] == "B" and row["repeat"] == 1 for row in reuse))
        self.assertLessEqual(len(reuse), 6)

    def test_expanded_task_current_prompt_embeds_every_frozen_skill_reference(self):
        task_id = "fastapi-technical-report-dev"
        root = self.prepare("expanded-bundle", task=[task_id], repeat=1)
        task = formal.read_jsonl(root / "tasks.jsonl")[0]
        pilot_task = next(t for t in base.read_tasks(self.pilot / "tasks.jsonl") if t["kind"] == task["kind"])
        pilot_case = self.pilot / "frozen" / pilot_task["id"] / "current"
        expected_bundle = json.loads((pilot_case / "bundle-manifest.json").read_text(encoding="utf-8"))
        plain_case = root / "frozen" / task_id / "A"
        current_case = root / "frozen" / task_id / "B"
        plain_records = formal.prompt_source_records((plain_case / "prompt.txt").read_text(encoding="utf-8"))
        current_records = formal.prompt_source_records((current_case / "prompt.txt").read_text(encoding="utf-8"))
        self.assertEqual(sum(r.get("role") == "skill_reference" for r in plain_records), 0)
        actual_skills = [r for r in current_records if r.get("role") == "skill_reference"]
        self.assertEqual(len(actual_skills), len(expected_bundle))
        self.assertEqual({r["path"] for r in actual_skills}, set(expected_bundle))
        for row in actual_skills:
            self.assertEqual(row["sha256"], expected_bundle[row["path"]])
            self.assertEqual(base.digest_bytes(row["content"].encode("utf-8")), row["sha256"])
            self.assertEqual(base.sha(current_case / row["path"]), row["sha256"])
        self.assertEqual(json.loads((current_case / "bundle-manifest.json").read_text(encoding="utf-8")), expected_bundle)
        formal.verify_formal(root)

    def test_expanded_task_selected_skill_subset_is_exact_and_hash_verified(self):
        task_id = "fastapi-technical-report-dev"
        pilot_task = next(t for t in base.read_tasks(self.pilot / "tasks.jsonl") if t["kind"] == "technical-report")
        pilot_case = self.pilot / "frozen" / pilot_task["id"] / "current"
        available = json.loads((pilot_case / "bundle-manifest.json").read_text(encoding="utf-8"))
        selected = ["skills/oh-my-technology/references/technical-report.md",
                    "skills/word-document/references/evidence.md"]
        self.assertTrue(set(selected) <= set(available))
        config = self.root / "subset.json"
        config.write_text(json.dumps({"conditions": [{"id": "E4-ondemand", "base_condition": "plain",
                                                      "prompt_append": "Use only these selected process references.",
                                                      "extra_sources": [], "skill_files": selected}]}), encoding="utf-8")
        args = Namespace(pilot_run=self.pilot, tasks=self.tasks, data_root=self.data, out=self.root / "subset-run",
                         repeat=1, seed=23, split=["development"], task=[task_id], condition=None,
                         conditions_config=config, context_root=None, reuse_from=None)
        root = formal.prepare(args)
        case = root / "frozen" / task_id / "E4-ondemand"
        records = formal.prompt_source_records((case / "prompt.txt").read_text(encoding="utf-8"))
        actual = [r for r in records if r.get("role") == "skill_reference"]
        self.assertEqual({r["path"] for r in actual}, set(selected))
        formal.verify_formal(root)

    def test_serial_resume_preserves_failed_attempt_then_completes(self):
        root = self.prepare("resume", task=["scifact-0009-train-dev"], condition=["A"], repeat=1)
        job = formal.read_jsonl(root / "schedule.jsonl")[0]
        task = formal.read_jsonl(root / "tasks.jsonl")[0]
        args = Namespace(run=root, model=formal.MODEL, timeout=10, max_attempts=3, resume=False, jobs=1)

        def failed(_root, row, _task, attempt, _args):
            attempt.mkdir(parents=True, exist_ok=False)
            base.dump(attempt / "run.json", {"job_id": row["job_id"], "execution_state": "timeout",
                                              "generation_observed": False, "turn_completed": True,
                                              "usage": {"input_tokens": 5}, "error": "temporary runner failure"})
            raise RuntimeError("temporary runner failure")

        with patch.object(formal, "run_attempt", side_effect=failed):
            self.assertEqual(formal.run(args), 1)
        attempt1 = root / "attempts" / job["job_id"] / "attempt-01"
        self.assertEqual(formal.load_json(attempt1 / "run.json")["generation_observed"], False)
        self.assertIn("temporary runner failure", formal.load_json(attempt1 / "run.json")["error"])

        def succeeded(_root, row, _task, attempt, _args):
            attempt.mkdir(parents=True, exist_ok=False)
            result = {"job_id": row["job_id"], "task_id": row["task_id"], "condition": row["condition"],
                      "repeat": row["repeat"], "execution_state": "execution_complete", "generation_observed": True,
                      "turn_completed": True, "generation_complete": True,
                      "response_json": "valid", "response_schema": "pass",
                      "usage": {"input_tokens": 100, "cached_input_tokens": 10, "cache_write_input_tokens": 0,
                                "output_tokens": 20, "reasoning_output_tokens": 3}}
            base.dump(attempt / "run.json", result)
            return result

        args.resume = True
        with patch.object(formal, "run_attempt", side_effect=succeeded):
            self.assertEqual(formal.run(args), 0)
        attempt2 = root / "attempts" / job["job_id"] / "attempt-02"
        self.assertTrue((attempt1 / "run.json").is_file())
        self.assertTrue((attempt2 / "run.json").is_file())
        summary = formal.summarize(root)
        self.assertEqual(summary["usage"]["fields"]["input_tokens"]["total"], 105)
        self.assertTrue(summary["usage"]["fields"]["input_tokens"]["exact"])
        self.assertEqual(summary["usage"]["completed_turn_attempts"], 2)

    def test_missing_usage_is_not_silently_counted_as_zero(self):
        root = self.prepare("missing-usage", task=["scifact-0009-train-dev"], condition=["A"], repeat=1)
        job = formal.read_jsonl(root / "schedule.jsonl")[0]
        attempt = root / "attempts" / job["job_id"] / "attempt-01"
        attempt.mkdir(parents=True)
        base.dump(attempt / "run.json", {"generation_observed": True, "execution_state": "execution_complete",
                                          "turn_completed": True, "usage": {"input_tokens": 13}})
        row = formal.summarize(root)["usage"]["fields"]["output_tokens"]
        self.assertIsNone(row["total"])
        self.assertEqual(row["known_subtotal"], 0)
        self.assertFalse(row["exact"])


if __name__ == "__main__":
    unittest.main()
