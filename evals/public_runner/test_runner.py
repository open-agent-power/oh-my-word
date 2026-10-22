"""Offline runner tests; no model calls or scoring data."""
from __future__ import annotations

import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

import run_public_eval as runner


class PublicRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.data = self.root / "data"
        self.data.mkdir()
        material = self.data / "task" / "materials" / "evidence.txt"
        material.parent.mkdir(parents=True)
        material.write_text("The project uses typed routes.", encoding="utf-8")
        self.tasks = self.data / "tasks.jsonl"
        self.task = {"id": "qa-01", "kind": "factual-qa", "split": "development",
                     "request": "What does the evidence say?", "materials": [{
                         "path": "task/materials/evidence.txt", "sha256": runner.sha(material), "source_id": "S1"}],
                     "metadata": {"task_note": "not copied to the model"}}
        self.tasks.write_text(json.dumps(self.task) + "\n", encoding="utf-8")
        self.runs = self.root / "runs"

    def tearDown(self):
        self.temp.cleanup()

    def prepare(self):
        return runner.prepare(Namespace(tasks=self.tasks, data_root=self.data, runs=self.runs,
                                        run_id="offline-run", timeout=300))

    def test_unknown_scoring_fields_are_rejected(self):
        self.tasks.write_text(json.dumps({**self.task, "gold": {"answer": "hidden"}}) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Unexpected task fields"):
            runner.read_tasks(self.tasks)

    def test_prepare_freezes_context_and_relevant_bundle(self):
        root = self.prepare()
        task = json.loads((root / "tasks.jsonl").read_text(encoding="utf-8"))
        self.assertNotIn("metadata", task)
        self.assertNotIn("gold", task)
        freeze = json.loads((root / "freeze.json").read_text(encoding="utf-8"))
        self.assertEqual(freeze["evaluation_scope"], "context_only_generation")
        self.assertEqual(runner.sha(root / "freeze.json"), (root / "freeze.sha256").read_text().split()[0])
        plain = root / "frozen" / "qa-01" / "plain"
        current = root / "frozen" / "qa-01" / "current"
        self.assertIn("The project uses typed routes.", (plain / "prompt.txt").read_text(encoding="utf-8"))
        self.assertEqual(json.loads((plain / "bundle-manifest.json").read_text()), {})
        bundle = json.loads((current / "bundle-manifest.json").read_text(encoding="utf-8"))
        self.assertIn("skills/word-skills/SKILL.md", bundle)
        self.assertIn("skills/word-document/references/evidence.md", bundle)
        self.assertIn("shared/references/chinese-writing.md", bundle)
        self.assertTrue(runner.verify_frozen_case(current, root)[0])
        prompt = (current / "prompt.txt").read_text(encoding="utf-8")
        sources = prompt.split("Frozen source text", 1)[1]
        self.assertIn('"role":"material"', sources)
        self.assertIn('"role":"skill_reference"', sources)

    def test_execution_preserves_cli_trace_stderr_and_top_level_usage(self):
        root = self.prepare()
        response = json.dumps({"answer": "Typed routes.", "evidence": [], "limitations": []})
        events = [
            {"type": "thread.started", "thread_id": "thread-123"},
            {"type": "item.completed", "item": {"type": "agent_message", "text": response}},
            {"type": "turn.completed", "usage": {"input_tokens": 19, "output_tokens": 7}},
        ]
        stdout = "".join(json.dumps(e) + "\n" for e in events).encode()
        args = Namespace(model=runner.MODEL, timeout=300)
        with patch.object(runner, "execute", return_value=(0, stdout, b"diagnostic", False, "not_needed")):
            result = runner.run_one(root, json.loads((root / "tasks.jsonl").read_text()), "plain", args)
        directory = root / "runs" / "qa-01" / "plain"
        self.assertTrue(result["generation_countable"])
        self.assertEqual(result["thread_id"], "thread-123")
        self.assertEqual(result["usage"]["input_tokens"], 19)
        self.assertEqual((directory / "stderr.txt").read_bytes(), b"diagnostic")
        self.assertEqual((directory / "trace.jsonl").read_bytes(), stdout)
        self.assertEqual(result["agent_file_read"], "not_evaluated")
        self.assertEqual(result["material_ingestion"], "runner_verified")

    def test_failed_execution_is_preserved_and_not_counted(self):
        root = self.prepare()
        args = Namespace(model=runner.MODEL, timeout=300)
        with patch.object(runner, "execute", return_value=(3, b'{"type":"turn.failed"}\n', b"auth failed", False, "not_needed")):
            result = runner.run_one(root, json.loads((root / "tasks.jsonl").read_text()), "plain", args)
        directory = root / "runs" / "qa-01" / "plain"
        self.assertFalse(result["generation_countable"])
        self.assertEqual(result["execution_state"], "error")
        self.assertEqual((directory / "stderr.txt").read_bytes(), b"auth failed")
        self.assertTrue((directory / "run.json").is_file())
        self.assertIn("trace.jsonl", result["artifact_hashes"])


if __name__ == "__main__":
    unittest.main()
