# Public Word Skills runner

`prepare` creates a frozen, hash-verified snapshot and makes no model calls. `run --execute` launches one fresh ephemeral Codex context per task and condition. The runner accepts only the public task contract (`id`, `kind`, `split`, `request`, `materials`, optional `metadata`) and material records (`path`, `sha256`, `source_id`). It rejects unknown top-level fields, discards metadata before freezing, and never reads scoring-data.

Set `WORD_SKILLS_CODEX` to an executable path or put `codex` on PATH; no developer drive is assumed. Runs default to the ignored repository `eval-runs/` directory; `WORD_SKILLS_EVAL_RUNS` overrides it. The Windows absolute paths below describe the historical local pilot, not installation requirements for another machine.

The CLI repeatedly blocked known-safe local file reads. The pilot therefore measures **context-only generation**: the runner reads, hashes, and embeds every source file as JSON-escaped text. Both conditions receive identical task materials and the same JSON output contract. The current condition additionally receives frozen, relevant Skill/reference/schema text. Source records are marked as untrusted data. `run.json` records `evaluation_scope=context_only_generation`, `material_ingestion=runner_verified`, `agent_file_read=not_evaluated`, and `autonomous_tool_compliance=blocked_by_runtime`. This pilot cannot support claims about agent file-reading behavior or autonomous tool compliance.

For technical-report and design-spec tasks, the current bundle includes the relevant Word Skills, all linked technical and Word references, shared Chinese writing guidance, the task schema, and registry. Factual QA receives the general route and applicable evidence principles without being forced into document generation. Each condition has a unique workspace; only the frozen prompt and source copies for that case are present. The model receives source contents through stdin, not by reading those workspace files.

Example:

```powershell
$py = 'D:\XiangMuLuoDi\Development\oh-my-patent-v0.2.0-cnipa-20260930\oh-my-patent\.venv\Scripts\python.exe'
& $py 'D:\XiangMuLuoDi\Development\oh-my-patent-v0.2.0-cnipa-20260930\oh-my-patent\evals\public_runner\run_public_eval.py' prepare --tasks 'D:\XiangMuLuoDi\Development\word-skills-public-eval\data\tasks.jsonl' --data-root 'D:\XiangMuLuoDi\Development\word-skills-public-eval\data'
```

Inspect `freeze.json`, `freeze.sha256`, frozen task sources, prompts, and manifests before any model calls. Execution requires the exact requested `gpt-6-luna`; there is no replacement fallback. The runner uses low reasoning effort, disables ambient apps/plugins/memories/hooks and host Skill discovery, and keeps the read-only sandbox. It saves untouched `trace.jsonl`, separate `stderr.txt`, final response, usage and thread metadata where available, time, hashes, JSON/schema gates, and failed attempts. Missing model identity or usage remains unknown. It never marks outputs reviewed or generates DOCX/PDF artifacts.

The generation count requires a completed CLI turn, non-empty response, valid JSON, the shared output schema, and unchanged frozen inputs/workspace. It does not imply answer quality, actual agent-side file reading, or review. A failed gate stops the remaining queue and preserves the failed artifacts.

Domain writing also accepts `copyright-manual` and `patent-outline`. Their current-condition bundles select the corresponding domain entry and relevant references rather than a technical-report schema. A patent outline is a public-material writing exercise, not an application-readiness or novelty evaluation. Task materials and the shared response contract remain identical across paired conditions.

The response JSON Schema is now frozen with the case and passed through Codex's existing `--output-schema` option. `evidence_quote_audit` separately checks manifest-listed material paths and exact contiguous quote text. Failed or absent evidence remains visible; `generation_countable` continues to mean structural generation validity, not factual acceptance. An authentic quotation can still accompany a false conclusion, so `semantic_support` remains `not_automatically_evaluated` even when all literal quotes match.

`prepare --condition current` creates an explicitly single-condition **repair trial**, with its own frozen denominator. Do not merge it into an earlier A/B run or retry until the desired quality result appears. Preserve the original failed outputs and report runtime/usage separately. Offline schedule tests create synthetic temporary inputs; they do not depend on this machine's historical experiment directories, and they provide no model-quality evidence.
