# Import a fixed knowledge pack to RAGFlow

The real-service trial uses the upstream `v1.0.0-rc2` image, a local `bge-m3` embedding model, and the Go API's `parse_type: 1` / `parser_id: general` dataset fields. Model identifiers can be tenant model UUIDs (preferred when several instances exist) or `model@provider` names. The trial keeps an active set of eight sources / 80 chunks; the complete guideline remains in the earlier frozen pack. This is retrieval and delivery integration evidence, not a writing-quality benchmark.

`import_fixed.py` copies a verified frozen pack into a new output folder, creates a RAGFlow dataset, uploads each original source file, and adds the pack's existing chunks verbatim. It does not parse sources into new chunks. The generated `ragflow.json` binds remote document and chunk IDs to the copied pack's `kb_id`; it appears only after the full import succeeds. On failure, the copy retains `ragflow-import-journal.json` for diagnosis and has no active RAGFlow configuration.

Set the API key in `WORD_SKILLS_RAGFLOW_API_KEY` before running the importer. The URL must be loopback HTTP; requests use a 30-second maximum timeout, bypass proxies, and reject redirects. Rerunning requires a fresh `--out` directory and a new dataset `--name`; the importer does not retry mutations or delete partial remote datasets.

```powershell
$env:WORD_SKILLS_RAGFLOW_API_KEY = "<your-api-key>"
.venv\Scripts\python.exe tools\ragflow\import_fixed.py `
  --index outputs\knowledge-pack `
  --url http://127.0.0.1:9380 `
  --embedding-model bge-m3@Ollama `
  --name patent-kb-fixed-01 `
  --out outputs\ragflow\patent-kb-fixed-01
```

Use the output folder as the knowledge-pack path for retrieval. Keep it local because its `ragflow.json` contains the loopback endpoint and remote IDs; the API key itself is never written there.

An import journal without `state: complete`, or a completed journal without its configuration, disables retrieval from that output folder. There is no silent fallback to BM25 after a partial import. The original configless pack remains independently usable.
