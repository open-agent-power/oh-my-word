"""Write auditable source/provenance manifest for external formal-v1 data."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def record_file(root: Path, rel: str) -> dict:
    p = root / rel
    return {"path": rel.replace("\\", "/"), "bytes": p.stat().st_size, "sha256": sha(p)}


def record_score_file(scoring_root: Path, rel: str) -> dict:
    p=scoring_root/rel
    return {"path": "scoring-data/formal-v1/"+rel.replace("\\", "/"), "bytes": p.stat().st_size, "sha256": sha(p), "visibility":"scoring-only source annotations; never mount for generation"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("data_root", type=Path)
    args = ap.parse_args()
    root = args.data_root.resolve()
    items = [
        {"id":"scifact-data-v1","title":"SciFact","url":"https://github.com/allenai/scifact","version":{"repository_commit":"68b98a56d93e0f9da0d2aab4e6c3294699a0f72e","dataset_release":"release/latest (upstream URL is mutable)"},"license":{"claims_and_evidence":"CC BY 4.0","abstract_corpus":"ODC-By 1.0 (S2ORC attribution required)","scope":"data as identified by upstream SciFact documentation; not the code license"},"files":[record_file(root,"sources/scifact/raw/data.tar.gz"),record_file(root,"sources/scifact/raw/LICENSE.md")],"selection":"12-claim custom candidate-search subset; six development queries from train and six heldout queries from dev; one query per source paper, disjoint across splits; identical label-free candidate corpus within each split; no upstream test split used.","limitations":["Dataset archive URL is mutable; commit pins repository documentation, archive SHA-256 pins retrieved bytes.","Public benchmark data may be present in model pretraining.","Custom subset is not an official SciFact benchmark score."]},
        {"id":"cmrc2018-2018-cc-by-sa-4.0","title":"CMRC 2018","url":"https://github.com/ymcui/cmrc2018","version":{"repository_commit":"c0eb1b6ba219847457e6af3180da722bbeb656af","retrieved":"2026-10-20"},"license":{"data":"CC BY-SA 4.0, explicitly stated on official dataset site and LICENCE","attribution":"Yiming Cui et al., A Span-Extraction Dataset for Chinese Machine Reading Comprehension, EMNLP-IJCNLP 2019","derivative_subset":"Derived task materials retain source attribution and are shared under CC BY-SA 4.0; check compatibility before further redistribution."},"files":[record_file(root,"sources/cmrc2018/raw/cmrc2018_train.json"),record_file(root,"sources/cmrc2018/raw/cmrc2018_dev.json"),record_file(root,"sources/cmrc2018/raw/LICENCE"),record_file(root,"sources/cmrc2018/raw/cmrc2018_evaluate.py")],"selection":"12 custom Chinese short-answer reading tasks; one question per distinct passage, six from public train for development and six from public dev for heldout. Gold answers remain scoring-side.","limitations":["Short context-grounded Chinese QA replaces LongBench; it does not test LongBench long-context capability.","Subset is not an official CMRC2018 test score."]},
        {"id":"longbench-excluded","title":"LongBench candidate reviewed but excluded","url":"https://huggingface.co/datasets/THUDM/LongBench","version":{"repository_commit":"2e00731f8d0bff23dc4325161044d0ed8af94c1e","dataset_revision":"5e628be450b7e67fb7ae6e201bd6d8f7056f7672"},"license":{"code":"MIT (repository code only)","data":"No explicit data license declared in pinned dataset card; not treated as redistributable."},"files":[record_file(root,"sources/longbench/raw/data.zip"),record_file(root,"sources/longbench/raw/HF-DATASET-README.md")],"status":"excluded from tasks.jsonl and formal-v1-development.jsonl","reason":"Code MIT does not establish license for bundled benchmark data. Data archive retained only as a reviewed provenance artifact in this private local evaluation workspace; do not redistribute or use as task material."},
        {"id":"fastapi-code","title":"FastAPI code and documentation","url":"https://github.com/fastapi/fastapi","version":{"commit":"993899cc2021daec7ba170c7ee9bcefd45e8db43"},"license":{"project":"MIT"},"files":[record_file(root,"sources/projects/fastapi/raw/fastapi-993899cc2021daec7ba170c7ee9bcefd45e8db43.tar.gz")],"split":"development"},
        {"id":"express-code","title":"Express code","url":"https://github.com/expressjs/express","version":{"commit":"0dee2c52c7c873498f8ed7d8ee4ddd0a04d3ada8"},"license":{"project":"MIT"},"files":[record_file(root,"sources/projects/express/raw/express-0dee2c5.tar.gz")],"split":"development"},
        {"id":"express-docs","title":"Express documentation","url":"https://github.com/expressjs/expressjs.com","version":{"commit":"dee32dd56b459db85de61691934e28adfc6502f8"},"license":{"documentation":"CC BY 4.0"},"files":[record_file(root,"sources/projects/express-docs/raw/express-docs-dee32dd.tar.gz")],"split":"development","note":"Separate docs repository and commit are pinned independently from code."},
        {"id":"flask-code","title":"Flask code and documentation","url":"https://github.com/pallets/flask","version":{"commit":"d086db856be187255b8ec61ef409357393020f32"},"license":{"project":"BSD-3-Clause"},"files":[record_file(root,"sources/projects/flask/raw/flask-d086db8.tar.gz")],"split":"heldout"},
        {"id":"gin-code","title":"Gin code and documentation","url":"https://github.com/gin-gonic/gin","version":{"commit":"0f09c3a9b4626d9fe9979cf4d0521d6ae32ab646"},"license":{"project":"MIT"},"files":[record_file(root,"sources/projects/gin/raw/gin-0f09c3a.tar.gz")],"split":"heldout"},
        {"id":"omnidocbench-reviewed-not-included","title":"OmniDocBench parsing candidate","url":"https://huggingface.co/datasets/opendatalab/OmniDocBench","version":{"dataset_revision":"aa1ee96d106dbe53d0ae59474d75c6e6d9b53fec","annotation_file_commit":"d386947f7fc3bafdcd756c8485845a2f43a19875","repository_commit":"f133a71e9e91c3621c7ce8994200a7b394a06eb3","reviewed":"2026-10-20"},"license":{"dataset_card":"No SPDX/CC license metadata present.","publisher_statement":"Research purposes only; not for commercial use. PDFs collected from public channels/community contributions; non-distribution content removed.","code_repository":"Apache-2.0 applies to code repository, not independently to dataset pages."},"files":[record_file(root,"sources/omnidocbench/raw/HF-DATASET-README.md"),record_score_file(args.data_root.resolve().parent.parent / "scoring-data" / "formal-v1", "omnidocbench-source/OmniDocBench.json")],"status":"not included in formal tasks or parser sample","reason":"The pinned dataset is 1.55 GB and exposes page annotations with UUID image_path values that do not resolve to the named page images exposed by the HF repository. No reliable per-page image-to-annotation mapping was established, so no 24-page benchmark sample was frozen. No PDF pages redistributed.","limitation":"Do not treat the repository Apache-2.0 license as a license for source PDFs or page images."},
    ]
    manifest = {
        "dataset_id":"word-skills-public-eval-formal-v1",
        "created":"2026-10-20",
        "schema":"task rows: {id,kind,split,request,materials:[{path,sha256,source_id}],metadata}; material paths relative to data root",
        "data_root":"external local evaluation data/formal-v1",
        "task_files": {
            "development":{"path":"formal-v1-development.jsonl","bytes":(root/"formal-v1-development.jsonl").stat().st_size,"sha256":sha(root/"formal-v1-development.jsonl"),"task_count":16},
            "all_splits_internal":{"path":"tasks.jsonl","bytes":(root/"tasks.jsonl").stat().st_size,"sha256":sha(root/"tasks.jsonl"),"task_count":32,"visibility":"Do not give to development runner before heldout evaluation is authorized."},
        },
        "sources":items,
        "known_limitations":["Scoring gold is separate under sibling scoring-data/formal-v1; development-gold.jsonl and heldout-gold.jsonl are split separately. Never mount heldout-gold.jsonl in the generation environment.","Writing rubrics are unreviewed source-derived checklists, not expert gold.","Task excerpts are bounded, retain exact original path/line ranges and source hashes in task metadata; full project archives are kept locally for provenance.","No model generation or benchmark result is included in this data package.","LongBench was excluded because data license is unspecified; CMRC2018 is a licensed short-answer replacement, not equivalent long-context evaluation.","OmniDocBench 24-page parsing sample was not frozen because the current HF annotation/image mapping could not be reliably paired; see source record."]
    }
    out=root/"dataset-manifest.json"
    out.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"path":str(out),"sha256":sha(out),"sources":len(items)},ensure_ascii=False))


if __name__ == "__main__":
    main()
