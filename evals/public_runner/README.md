# Public Word Skills runner

`prepare` creates a frozen, hash-verified snapshot and makes no model calls. `run --execute` launches one fresh ephemeral Codex context per task and condition. The runner accepts only the public task contract (`id`, `kind`, `split`, `request`, `materials`, optional `metadata`) and material records (`path`, `sha256`, `source_id`). It rejects unknown top-level fields, discards metadata before freezing, and never reads scoring-data.

The CLI repeatedly blocked known-safe local file reads. The pilot therefore measures **context-only generation**: the runner reads, hashes, and embeds every source file as JSON-escaped text. Both conditions receive identical task materials and the same JSON output contract. The current condition additionally receives frozen, relevant Skill/reference/schema text. Source records are marked as untrusted data. `run.json` records `evaluation_scope=context_only_generation`, `material_ingestion=runner_verified`, `agent_file_read=not_evaluated`, and `autonomous_tool_compliance=blocked_by_runtime`. This pilot cannot support claims about agent file-reading behavior or autonomous tool compliance.

For technical-report and design-spec tasks, the current bundle includes the relevant Word Skills, all linked technical and Word references, shared Chinese writing guidance, the task schema, and registry. Factual QA receives the general route and applicable evidence principles without being forced into document generation. Each condition has a unique workspace; only the frozen prompt and source copies for that case are present. The model receives source contents through stdin, not by reading those workspace files.

Example:

```powershell
$py = 'D:\XiangMuLuoDi\Development\oh-my-patent-v0.2.0-cnipa-20260930\oh-my-patent\.venv\Scripts\python.exe'
& $py 'D:\XiangMuLuoDi\Development\oh-my-patent-v0.2.0-cnipa-20260930\oh-my-patent\evals\public_runner\run_public_eval.py' prepare --tasks 'D:\XiangMuLuoDi\Development\word-skills-public-eval\data\tasks.jsonl' --data-root 'D:\XiangMuLuoDi\Development\word-skills-public-eval\data'
```

Inspect `freeze.json`, `freeze.sha256`, frozen task sources, prompts, and manifests before any model calls. Execution requires the exact requested `gpt-6-luna`; there is no replacement fallback. The runner uses low reasoning effort, disables ambient apps/plugins/memories/hooks and host Skill discovery, and keeps the read-only sandbox. It saves untouched `trace.jsonl`, separate `stderr.txt`, final response, usage and thread metadata where available, time, hashes, JSON/schema gates, and failed attempts. Missing model identity or usage remains unknown. It never marks outputs reviewed or generates DOCX/PDF artifacts.

The generation count requires a completed CLI turn, non-empty response, valid JSON, the shared output schema, and unchanged frozen inputs/workspace. It does not imply answer quality, actual agent-side file reading, or review. A failed gate stops the remaining queue and preserves the failed artifacts.
