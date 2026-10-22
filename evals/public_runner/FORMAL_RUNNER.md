# Formal public runner

`formal_runner.py` is an extension alongside the frozen pilot runner. `prepare` only verifies and freezes public inputs, task/condition contexts, and a seeded shuffled schedule. `run` starts a fresh isolated Codex process and workspace for each job. It defaults to one job; `--jobs` accepts 1–3. Failed attempts, stdout trace, stderr, response, and metadata remain in numbered attempt folders. `--resume` skips observed generations and retries unfinished jobs up to `--max-attempts`. Two consecutive classified backend/model/auth failures stop new scheduling; in-flight jobs finish and are saved.

The default A/B conditions use plain and current contexts. The optional condition config supports `base_condition`, `prompt_append`, hash-verified `extra_sources`, and a selected subset of frozen `skill_files`. Use those fields to define deterministic host-side retrieval or style-reference conditions after their exact protocols are frozen. Nothing here evaluates agent-side file reads: sources are runner-verified and embedded as context.

Prepare the development AB schedule without making model calls:

```powershell
$py = 'D:\XiangMuLuoDi\Development\oh-my-patent-v0.2.0-cnipa-20260930\oh-my-patent\.venv\Scripts\python.exe'
$runner = 'D:\XiangMuLuoDi\Development\oh-my-patent-v0.2.0-cnipa-20260930\oh-my-patent\evals\public_runner\formal_runner.py'
& $py $runner prepare --pilot-run 'D:\XiangMuLuoDi\Development\word-skills-public-eval\runs\public-pilot-context-20261020' --tasks 'D:\XiangMuLuoDi\Development\word-skills-public-eval\data\formal-v1\formal-v1-development.jsonl' --data-root 'D:\XiangMuLuoDi\Development\word-skills-public-eval\data\formal-v1' --out 'D:\XiangMuLuoDi\Development\word-skills-public-eval\runs\formal-v1-dev-ab-v4' --split development --repeat 3 --seed 20261020
```

After the root review gate, execute the prepared run with `formal_runner.py run --run 'D:\XiangMuLuoDi\Development\word-skills-public-eval\runs\formal-v1-dev-ab-v4' --jobs 3`. Add `--resume` only when continuing a prior attempt. A new run directory is required if the runner, condition text, task inputs, or schedule changes.

The current formal-v1 development package has 16 tasks, 2 conditions, and 3 repeats (96 scheduled jobs). Its task set does not overlap the 2026-10-20 pilot, so no B result is reusable; all 96 jobs will call the model. The pilot measured 240.469 seconds for 12 generations (about 20 seconds each). At that rate, 96 jobs would take roughly 32 minutes serially or 11 minutes at three-way concurrency; 192 jobs would take roughly 64 minutes serially or 21 minutes at three-way concurrency. These are linear estimates only; larger prompts and service contention can increase elapsed time. Keep concurrency capped at 3.

`generation_observed` means a completed response exists for scoring. It is separate from `generation_complete`, which requires a normal CLI exit and a completed, non-failed turn. The first observed response per job is retained for scoring, including responses from attempts that later report a non-zero process exit; reruns cannot replace an observed sample. `summarize` reports completed-job and observed-response counts separately. Resource usage totals include every non-reused attempt with a completed turn, including failed/retried jobs; reused pilot usage is excluded from new resource totals. A per-field total is `null` whenever any counted turn lacks that field, and a known subtotal is shown separately.
