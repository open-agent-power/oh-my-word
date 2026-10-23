import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from evals.content_support import probe


class ProbePreparationTests(unittest.TestCase):
    def setUp(self):
        runtime = tempfile.TemporaryDirectory()
        self.addCleanup(runtime.cleanup)
        cli = Path(runtime.name) / "codex-fixture"
        cli.write_bytes(b"synthetic-cli-identity-not-executable")
        for stub in (patch.object(probe, "CODEX", cli),
                     patch.object(probe, "cli_version", return_value="synthetic-test-runtime")):
            stub.start()
            self.addCleanup(stub.stop)

    def test_prepare_freezes_four_cases_and_sixteen_randomized_jobs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            corpus = root / "corpus.jsonl"
            doc = {"doc_id": 45638119, "title": "ALDH1 outcome", "abstract": [
                "s1", "s2", "s3", "s4", "Expression of ALDH1 detected by immunostaining correlated with poor prognosis.", "s6"]}
            corpus.write_text(json.dumps(doc) + "\n", encoding="utf-8")
            prepared = probe.prepare(root / "out", corpus, "test-run")
            probe.verify(prepared)
            tasks = json.loads((prepared / "tasks.json").read_text(encoding="utf-8"))
            gold = json.loads((prepared / "hidden-expected.json").read_text(encoding="utf-8"))
            schedule = json.loads((prepared / "schedule.json").read_text(encoding="utf-8"))
            self.assertEqual(len(tasks), 4)
            self.assertEqual([x["expected_relation"] for x in gold], ["contradicted", "supported", "insufficient", "not_shipped_claim"])
            self.assertEqual(len(schedule["jobs"]), 16)
            self.assertEqual(len({(x["case_id"], x["condition"], x["repeat"]) for x in schedule["jobs"]}), 16)
            self.assertEqual(schedule["max_jobs"], 2)
            for case in tasks:
                prompt_a = (prepared / "prompts" / f"{case['id']}-A.txt").read_text(encoding="utf-8")
                prompt_b = (prepared / "prompts" / f"{case['id']}-B.txt").read_text(encoding="utf-8")
                self.assertEqual(prompt_a.split("\n\nClaim:\n", 1)[1], prompt_b.split("\n\nClaim:\n", 1)[1])
            p_b = (prepared / "prompts/proposal-not-shipped-B.txt").read_text(encoding="utf-8")
            self.assertIn("population, and time", p_b)
            self.assertIn("proposal or planned capability", p_b)
            synthetic = (prepared / "data/proposal-synthetic.txt").read_text(encoding="utf-8")
            self.assertIn("HOST-AUTHORED SYNTHETIC SOURCE", synthetic)
            self.assertIn("not implemented and not shipped", synthetic)

    def test_verification_rejects_prompt_change(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            corpus = root / "corpus.jsonl"
            doc = {"doc_id": 45638119, "title": "ALDH1", "abstract": ["a", "b", "c", "d", "e", "f"]}
            corpus.write_text(json.dumps(doc) + "\n", encoding="utf-8")
            prepared = probe.prepare(root / "out", corpus, "test-run")
            prompt = prepared / "prompts/aldh-better-contradiction-A.txt"
            prompt.write_text(prompt.read_text(encoding="utf-8") + " changed", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "frozen input changed"):
                probe.verify(prepared)

    def test_verification_rejects_changed_cli_identity(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            corpus = root / "corpus.jsonl"
            corpus.write_text(json.dumps({"doc_id": 45638119, "title": "fixture", "abstract": ["a", "b", "c", "d", "e", "f"]}) + "\n", encoding="utf-8")
            prepared = probe.prepare(root / "out", corpus, "test-run")
            probe.CODEX.write_bytes(b"changed synthetic CLI")
            with self.assertRaisesRegex(ValueError, "CLI binary changed"):
                probe.verify(prepared)

    def test_missing_cli_fails_before_creating_run(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            corpus = root / "corpus.jsonl"
            corpus.write_text("", encoding="utf-8")
            with patch.object(probe, "CODEX", root / "missing"):
                with self.assertRaisesRegex(FileNotFoundError, "WORD_SKILLS_CODEX"):
                    probe.prepare(root / "out", corpus, "test-run")
            self.assertFalse((root / "out").exists())


def test_cli_version_uses_portable_argument_array():
    import sys
    # Use the current Python as a harmless --version executable, with no shell.
    with patch.object(probe, "CODEX", Path(sys.executable)):
        assert "Python" in probe.cli_version()


if __name__ == "__main__":
    unittest.main()
