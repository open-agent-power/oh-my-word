# Public-source reuse trial

Run from the `oh-my-patent` package root with its virtual environment. Each run needs a new output directory.

```powershell
.\.venv\Scripts\python.exe evals\reuse\trial.py `
  --project 'D:\XiangMuLuoDi\Development\word-skills-reuse-trial\public-project' `
  --knowledge 'PATH_TO_INDEX' `
  --out 'D:\XiangMuLuoDi\Development\word-skills-reuse-trial\business-trial-rag' `
  --soffice 'PATH_TO_SOFFICE' `
  --pdftoppm 'PATH_TO_PDFTOPPM'
```

Omit `--knowledge` for the no-index baseline. `--manual-phrase` changes a sentence in the operation manual, allowing a fresh run to verify that edited wording changes generated files. The runner invokes the existing `copyright prepare`, `copyright select`, `copyright package --draft`, and patent template/build commands. It selects all five runtime Python files and records the reason for each. It captures three real CLI invocations from the supplied source tree.

Outputs include the source inventory and selection, manual, source and manual DOCX/PDF/page images, two-claim patent Markdown/DOCX/PDF/page images, knowledge audit when supplied, command log, and `trial-summary.json`. Human review remains pending. The patent draft describes implementation details from the public release and makes no novelty or ownership claim.

For a RAGFlow pack, supply its API key through `WORD_SKILLS_RAGFLOW_API_KEY`. The current machine has a local `D:\XiangMuLuoDi\Development\word-skills-reuse-trial\RUN.ps1` that starts the existing Docker Compose services, reads the local credential file into the child environment, and runs this trial into a fresh folder. The credential file is excluded from delivered materials. This convenience script uses local installation paths; portable use requires the flags above.

The public source archive, PyPI sdist and attribution record are in `D:\XiangMuLuoDi\Development\word-skills-reuse-trial\public-project-provenance` and adjacent `downloads`/`public-project` folders.
