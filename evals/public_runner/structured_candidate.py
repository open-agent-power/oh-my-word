#!/usr/bin/env python3
"""Opt-in structured-output candidate wrapper for the frozen public runner.

The wrapper patches only the in-process execute callable to add Codex CLI's
--output-schema flag. It never changes the frozen runner or base runner files.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
FORMAL_PATH = HERE / "formal_runner.py"
SCHEMAS = {"qa": HERE / "schema_qa.json", "writing": HERE / "schema_writing.json"}
MODEL_PIN = "gpt-6-luna"
AUDIT_LOCK = threading.Lock()


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_formal():
    sys.path.insert(0, str(HERE))
    spec = importlib.util.spec_from_file_location("formal_runner_candidate_import", FORMAL_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load the frozen formal runner")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def schema_kind(prompt: str) -> str:
    match = re.search(r"(?:^|\n\n)Task kind: (factual-qa|technical-report|design-spec)\n", prompt)
    if match is None:
        raise ValueError("Prompt lacks a recognized frozen task-kind header")
    return "qa" if match.group(1) == "factual-qa" else "writing"


def schema_for_prompt(prompt: str) -> Path:
    return SCHEMAS[schema_kind(prompt)]


def add_schema_argument(argv: list[str], schema_path: Path) -> list[str]:
    if "--output-schema" in argv:
        raise ValueError("Refusing to layer candidate schema onto an existing output-schema argument")
    if not argv or argv[-1] != "-":
        raise ValueError("Expected the frozen runner's stdin prompt marker as final CLI argument")
    return [*argv[:-1], "--output-schema", str(schema_path.resolve()), argv[-1]]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_exec(run_root: Path, row: dict) -> None:
    path = run_root / "candidate-exec.jsonl"
    encoded = (json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    with AUDIT_LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("ab") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())


def install_execute_patch(formal, run_root: Path) -> None:
    base = formal.base
    original = base.execute

    def candidate_execute(argv: list[str], cwd: Path, prompt: str, timeout: int):
        kind = schema_kind(prompt)
        schema_path = SCHEMAS[kind]
        schema_sha = sha(schema_path)
        patched_argv = add_schema_argument(argv, schema_path)
        attempt_root = cwd.parent
        started = now()
        row = {"started_utc": started, "task_kind": kind, "schema_path": str(schema_path.resolve()),
               "schema_sha256": schema_sha, "argv": patched_argv, "cwd": str(cwd),
               "timeout_seconds": timeout}
        try:
            returncode, stdout, stderr, timed_out, termination = original(patched_argv, cwd, prompt, timeout)
            row.update({"return_code": returncode, "timed_out": timed_out, "process_termination": termination,
                        "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
                        "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
                        "stdout_bytes": len(stdout), "stderr_bytes": len(stderr), "status": "returned"})
            return returncode, stdout, stderr, timed_out, termination
        except BaseException as exc:
            row.update({"status": "raised", "exception_type": type(exc).__name__,
                        "exception": str(exc)[:1000]})
            raise
        finally:
            record_exec(run_root, row)

    base.execute = candidate_execute


def cli_evidence(codex: Path) -> dict:
    help_result = subprocess.run([str(codex), "exec", "--help"], stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, check=False, timeout=30)
    combined = help_result.stdout + help_result.stderr
    text = combined.decode("utf-8", errors="replace")
    if help_result.returncode != 0 or "--output-schema <FILE>" not in text:
        raise RuntimeError("Local Codex CLI help did not verify exec --output-schema <FILE>")
    version = subprocess.run([str(codex), "--version"], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, check=False, timeout=30)
    return {"codex_executable": str(codex.resolve()), "help_return_code": help_result.returncode,
            "help_sha256": hashlib.sha256(combined).hexdigest(),
            "verified_option": "codex exec --output-schema <FILE>",
            "version_return_code": version.returncode,
            "version_output": (version.stdout + version.stderr).decode("utf-8", errors="replace").strip()[:200]}


def candidate_freeze(run_root: Path, codex: Path) -> dict:
    formal = load_formal()
    formal_freeze = formal.verify_formal(run_root)
    base = formal.base
    if base.sha(Path(base.__file__)) != formal_freeze["base_runner_sha256"]:
        raise ValueError("Frozen base runner hash mismatch")
    if base.sha(FORMAL_PATH) != formal_freeze["runner_sha256"]:
        raise ValueError("Frozen formal runner hash mismatch")
    schemas = {}
    for kind, path in SCHEMAS.items():
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("type") != "object":
            raise ValueError(f"Structured output schema root must be an object: {kind}")
        schemas[kind] = {"path": path.name, "sha256": sha(path)}
    return {"schema_version": 1, "created_utc": now(), "candidate_id": "structured-output-v1",
            "formal_freeze_sha256": sha(run_root / "formal-freeze.json"),
            "formal_runner_sha256": sha(FORMAL_PATH), "base_runner_sha256": sha(Path(base.__file__)),
            "wrapper_sha256": sha(Path(__file__).resolve()), "schemas": schemas,
            "cli_evidence": cli_evidence(codex),
            "model_pin": MODEL_PIN, "output_schema_injection": "exec argv; immediately before stdin '-'",
            "output_contract_factor": "Candidate schema requires every declared field and rejects additional fields; this narrows field-level freedom relative to unconstrained formal B. It is a separate structured-output factor, not a claim of identical output freedom.",
            "execution_scope": "candidate-only; formal base and formal freeze are unchanged",
            "semantic_guarantee": "schema constrains response shape only; semantic quality is evaluated separately"}


def write_candidate_freeze(run_root: Path, codex: Path) -> Path:
    run_root = run_root.resolve()
    result = candidate_freeze(run_root, codex)
    path = run_root / "candidate-freeze.json"
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)
    (run_root / "candidate-freeze.sha256").write_text(f"{sha(path)}  candidate-freeze.json\n", encoding="ascii")
    return path


def verify_candidate_freeze(run_root: Path, codex: Path) -> dict:
    path = run_root / "candidate-freeze.json"
    sidecar = run_root / "candidate-freeze.sha256"
    if not path.is_file() or not sidecar.is_file():
        raise ValueError("Run candidate freeze first; candidate freeze is missing")
    expected = sidecar.read_text(encoding="ascii").split()[0]
    if sha(path) != expected:
        raise ValueError("Candidate freeze checksum mismatch")
    frozen = json.loads(path.read_text(encoding="utf-8"))
    formal = load_formal()
    formal_freeze = formal.verify_formal(run_root)
    check = {"formal_freeze_sha256": sha(run_root / "formal-freeze.json"),
             "formal_runner_sha256": sha(FORMAL_PATH),
             "base_runner_sha256": sha(Path(formal.base.__file__)),
             "wrapper_sha256": sha(Path(__file__).resolve()),
             "schemas": {kind: {"path": path.name, "sha256": sha(path)} for kind, path in SCHEMAS.items()}}
    for key, value in check.items():
        if frozen.get(key) != value:
            raise ValueError(f"Candidate freeze mismatch: {key}")
    if frozen.get("cli_evidence") != cli_evidence(codex):
        raise ValueError("Local Codex CLI help/version evidence changed since candidate freeze")
    if formal.base.sha(Path(formal.base.__file__)) != formal_freeze["base_runner_sha256"]:
        raise ValueError("Formal base runner changed after formal freeze")
    if formal.base.sha(FORMAL_PATH) != formal_freeze["runner_sha256"]:
        raise ValueError("Formal runner changed after formal freeze")
    if frozen.get("model_pin") != MODEL_PIN or formal_freeze.get("model") != MODEL_PIN:
        raise ValueError("Candidate or formal model pin mismatch")
    return frozen


def self_test(codex: Path) -> dict:
    evidence = cli_evidence(codex)
    qa = json.loads(SCHEMAS["qa"].read_text(encoding="utf-8"))
    writing = json.loads(SCHEMAS["writing"].read_text(encoding="utf-8"))
    formal = load_formal()
    qa_evidence = qa["properties"]["evidence"]
    writing_props = writing["properties"]
    draft_props = writing_props["draft"]["properties"]
    section_props = draft_props["sections"]["items"]["properties"]
    block_options = section_props["blocks"]["items"]["anyOf"]
    qa_item = qa_evidence["items"]
    writing_evidence = writing_props["evidence"]
    contract_ok = (
        qa.get("required") == ["answer", "evidence", "limitations"] and
        qa["properties"]["answer"].get("type") == "string" and
        qa_evidence.get("type") == "array" and
        set(qa_item.get("required", [])) >= {"claim", "material_path", "quote"} and
        all(qa_item["properties"][key].get("type") == "string" for key in ("claim", "material_path", "quote")) and
        qa["properties"]["limitations"].get("items", {}).get("type") == "string" and
        writing.get("required") == ["draft", "evidence", "limitations"] and
        writing_props["draft"].get("required") == ["title", "sections"] and
        draft_props["sections"].get("minItems") == 1 and
        set(draft_props["sections"]["items"].get("required", [])) == {"title", "blocks"} and
        len(block_options) == 2 and
        {tuple(option["properties"]["type"].get("enum", [])) for option in block_options} == {("paragraph",), ("table",)} and
        set(block_options[0].get("required", [])) == {"type", "text"} and
        writing_evidence.get("type") == "array" and
        set(writing_evidence["items"].get("required", [])) >= {"claim", "material_path", "quote"} and
        all(writing_evidence["items"]["properties"][key].get("type") == "string"
            for key in ("claim", "material_path", "quote")) and
        writing_props["limitations"].get("type") == "array" and
        writing_props["limitations"].get("items", {}).get("type") == "string"
    )
    if not contract_ok:
        raise AssertionError("JSON Schemas do not enforce the shared QA/writing response contract")
    for schema in (qa, writing):
        stack = [schema]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                if node.get("type") == "object":
                    properties = node.get("properties", {})
                    if node.get("additionalProperties") is not False or set(node.get("required", [])) != set(properties):
                        raise AssertionError("Structured-output object must require every property and reject extras")
                if "oneOf" in node or "const" in node or "minLength" in node:
                    raise AssertionError("Schema uses an unsupported or disallowed structured-output keyword")
                stack.extend(node.values())
            elif isinstance(node, list):
                stack.extend(node)
    cases = {
        "factual-qa": ({"answer": "fact", "evidence": [{"claim": "x", "material_path": "m", "quote": "q"}],
                        "limitations": []}, "qa"),
        "technical-report": ({"draft": {"title": "T", "sections": [{"title": "S", "blocks": [
            {"type": "paragraph", "text": "p"}, {"type": "table", "headers": ["h"], "rows": [["v"]]}]}]},
            "evidence": [], "limitations": []}, "writing")}
    for kind, (obj, schema_key) in cases.items():
        prompt = "COMMON\n\nTask kind: " + kind + "\nRequest:\nexample"
        if schema_kind(prompt) != schema_key:
            raise AssertionError("kind-to-schema mapping mismatch")
        if add_schema_argument(["codex", "exec", "--json", "-"], SCHEMAS[schema_key])[-3:] != [
                "--output-schema", str(SCHEMAS[schema_key].resolve()), "-"]:
            raise AssertionError("CLI schema argument is not injected before stdin marker")
        status = formal.base.validate_response(json.dumps(obj, ensure_ascii=False), kind)
        if status != ("valid", "pass"):
            raise AssertionError(f"shared response contract rejected {kind} fixture: {status}")
    with tempfile.TemporaryDirectory(prefix="structured-candidate-selftest-") as tmp:
        audit_root = Path(tmp)
        captured = {}
        base = formal.base
        original = base.execute

        def fake_execute(argv, cwd, prompt, timeout):
            captured["argv"] = argv
            return 0, b"offline-trace", b"", False, "not_needed"

        base.execute = fake_execute
        try:
            install_execute_patch(formal, audit_root)
            fake_prompt = "COMMON\n\nTask kind: factual-qa\nRequest:\nexample"
            base.execute(["codex", "exec", "--json", "-"], audit_root / "workspace", fake_prompt, 5)
        finally:
            base.execute = original
        rows = [json.loads(line) for line in (audit_root / "candidate-exec.jsonl").read_text("utf-8").splitlines()]
        expected = ["--output-schema", str(SCHEMAS["qa"].resolve()), "-"]
        if captured.get("argv", [])[-3:] != expected or rows[0].get("argv", [])[-3:] != expected:
            raise AssertionError("patched execute did not pass and record the exact output-schema argv")
        if rows[0].get("schema_sha256") != sha(SCHEMAS["qa"]):
            raise AssertionError("candidate execution log does not pin schema hash")
    if formal.base.validate_response('{"answer":"x","evidence":[],"limitations":[]}', "technical-report")[1] != "fail":
        raise AssertionError("QA shape unexpectedly passed the writing contract")
    if formal.base.validate_response('{"answer":"","evidence":[],"limitations":[]}', "factual-qa")[1] != "fail":
        raise AssertionError("Local response gate must reject an empty QA answer")
    if not qa.get("required") == ["answer", "evidence", "limitations"]:
        raise AssertionError("QA schema diverges from common contract")
    if not writing.get("required") == ["draft", "evidence", "limitations"]:
        raise AssertionError("Writing schema diverges from common contract")
    return {"status": "passed", "checks": ["local CLI option observed", "schema JSON parses",
            "nested QA/writing schema contract",
            "kind mapping", "argv wiring before stdin marker", "common response-contract fixtures",
            "cross-kind rejection", "patched execute argv and audit log"], "cli_evidence": evidence,
            "schema_hashes": {k: sha(v) for k, v in SCHEMAS.items()},
            "model_calls": 0}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("self-test", help="Check local CLI wiring and schemas without model calls")
    p.add_argument("--codex", type=Path, default=Path(r"D:\Kaifa-tool\Runtime\Volta\bin\codex.cmd"))
    p.set_defaults(action="self-test")
    p = sub.add_parser("freeze", help="Write a separate candidate freeze beside an already prepared formal run")
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--codex", type=Path, default=Path(r"D:\Kaifa-tool\Runtime\Volta\bin\codex.cmd"))
    p.set_defaults(action="freeze")
    p = sub.add_parser("run", help="Run a candidate through the unchanged formal runner")
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--resume", action="store_true")
    p.add_argument("--max-attempts", type=int, default=3)
    p.add_argument("--timeout", type=int, default=900)
    p.add_argument("--model", default=MODEL_PIN)
    p.add_argument("--jobs", type=int, default=1)
    p.add_argument("--codex", type=Path, default=Path(r"D:\Kaifa-tool\Runtime\Volta\bin\codex.cmd"))
    p.set_defaults(action="run")
    args = parser.parse_args()
    if args.action == "self-test":
        print(json.dumps(self_test(args.codex.resolve()), ensure_ascii=False, indent=2))
        return 0
    run_root = args.run.resolve()
    if args.action == "freeze":
        print(write_candidate_freeze(run_root, args.codex.resolve()))
        return 0
    if args.model != MODEL_PIN:
        parser.error(f"Model is pinned to {MODEL_PIN}; substitution is refused")
    frozen = verify_candidate_freeze(run_root, args.codex.resolve())
    formal = load_formal()
    original = formal.base.execute
    install_execute_patch(formal, run_root)
    try:
        ns = argparse.Namespace(action="run", run=run_root, resume=args.resume, max_attempts=args.max_attempts,
                                timeout=args.timeout, model=args.model, jobs=args.jobs)
        result = formal.run(ns)
    finally:
        formal.base.execute = original
    print(json.dumps({"return_code": result, "candidate_freeze_sha256": sha(run_root / "candidate-freeze.json"),
                      "formal_freeze_sha256": frozen["formal_freeze_sha256"]}, ensure_ascii=False))
    return int(result)


if __name__ == "__main__":
    raise SystemExit(main())
