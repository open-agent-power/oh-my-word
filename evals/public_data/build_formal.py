"""Build source-backed formal-v1 public evaluation tasks.

Only standard-library transformations are used. Upstream archives are retained
under the external data root; task materials are bounded and hashed separately.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
from pathlib import Path


FASTAPI = "993899cc2021daec7ba170c7ee9bcefd45e8db43"
FLASK = "d086db856be187255b8ec61ef409357393020f32"
EXPRESS = "0dee2c52c7c873498f8ed7d8ee4ddd0a04d3ada8"
EXPRESS_DOCS = "dee32dd56b459db85de61691934e28adfc6502f8"
GIN = "0f09c3a9b4626d9fe9979cf4d0521d6ae32ab646"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def source_dir(raw: Path, stem: str, archive: Path | None = None) -> Path:
    dirs = list(raw.glob(stem + "*") )
    dirs = [p for p in dirs if p.is_dir()]
    if dirs:
        return dirs[0]
    if archive is None:
        raise FileNotFoundError(stem)
    out = raw / stem
    out.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:gz") as tf:
        rootname = tf.getmembers()[0].name.split("/")[0]
        tf.extractall(raw, filter="data")
    dirs = [p for p in raw.iterdir() if p.is_dir() and p.name == rootname]
    if not dirs:
        raise FileNotFoundError(rootname)
    return dirs[0]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("data_root", type=Path)
    ap.add_argument("scoring_root", type=Path)
    ap.add_argument("--pilot-view", action="store_true", help="write development-only view")
    args = ap.parse_args()
    root, scoring = args.data_root.resolve(), args.scoring_root.resolve()
    sources = root / "sources"
    tasks: list[dict] = []
    gold: list[dict] = []

    # SciFact: use train claims as development tasks. The shared corpus is
    # label-free and identical across tasks, unlike the evidence-only pilot.
    sfraw = sources / "scifact" / "raw"
    sfarchive = sfraw / "data.tar.gz"
    sfdir = sfraw / "data"
    if not sfdir.exists():
        with tarfile.open(sfarchive, "r:gz") as tf:
            tf.extractall(sfraw, filter="data")
        if not (sfraw / "data").exists():
            sfdir = next(p for p in sfraw.iterdir() if p.is_dir() and (p / "claims_train.jsonl").exists())
    train = [json.loads(x) for x in (sfdir / "claims_train.jsonl").read_text(encoding="utf-8").splitlines()]
    dev = [json.loads(x) for x in (sfdir / "claims_dev.jsonl").read_text(encoding="utf-8").splitlines()]
    corpus = [json.loads(x) for x in (sfdir / "corpus.jsonl").read_text(encoding="utf-8").splitlines()]
    bydoc = {str(r["doc_id"]): r for r in corpus}
    # Deterministic label-balanced candidate sample. Select 6 train claims
    # balanced across classes, avoiding pilot IDs and one evidence paper reuse.
    chosen = []
    used_docs = set()
    for label in ("SUPPORT", "CONTRADICT", "NOT_ENOUGH_INFO"):
        n = 0
        for c in train:
            ev = c.get("evidence", {})
            cited = [str(x) for x in c.get("cited_doc_ids", [])]
            docs = list(ev) if label != "NOT_ENOUGH_INFO" else cited
            if c.get("id") in {3, 42, 49, 51} or c.get("evidence_label") != label:
                continue
            if len(docs) != 1 or docs[0] in used_docs:
                continue
            chosen.append(c); used_docs.update(docs); n += 1
            if n == 2:
                break
    # Some versions encode labels only in evidence; derive selected label robustly.
    if len(chosen) != 6:
        chosen = []
        for label in ("SUPPORT", "CONTRADICT", "NOT_ENOUGH_INFO"):
            n = 0
            for c in train:
                ev = c.get("evidence", {})
                cited = [str(x) for x in c.get("cited_doc_ids", [])]
                if c.get("id") in {3, 42, 49, 51}:
                    continue
                actual = next((r["label"] for rs in ev.values() for r in rs), "NOT_ENOUGH_INFO")
                docs = list(ev) if actual != "NOT_ENOUGH_INFO" else cited
                if actual != label or len(docs) != 1 or any(d in used_docs for d in docs):
                    continue
                chosen.append(c); used_docs.update(docs); n += 1
                if n == 2: break
    # Include selected query papers plus a fixed deterministic distractor set.
    selected_doc_ids = set(used_docs)
    distractors = [r for r in corpus if str(r["doc_id"]) not in selected_doc_ids][:120]
    candidates = [bydoc[d] for d in sorted(selected_doc_ids, key=int)] + distractors
    cand_rel = "shared/scifact/candidate-corpus.jsonl"
    cand_path = root / cand_rel
    cand_path.parent.mkdir(parents=True, exist_ok=True)
    cand_path.write_text("".join(json.dumps({"doc_id": r["doc_id"], "title": r["title"], "abstract": r["abstract"]}, ensure_ascii=False) + "\n" for r in candidates), encoding="utf-8")
    cand_hash = sha(cand_path)
    for c in chosen:
        ev = c.get("evidence", {})
        evidence_records = []
        for did, rs in ev.items():
            evidence_records.extend({"doc_id": int(did), "label": r["label"], "sentences": r["sentences"]} for r in rs)
        label = evidence_records[0]["label"] if evidence_records else "NOT_ENOUGH_INFO"
        tid = f"scifact-{int(c['id']):04d}-train-dev"
        tasks.append({"id": tid, "kind": "factual-qa", "split": "development", "request": "Using the supplied scientific-abstract candidate corpus, assess the claim. Return exactly one label (SUPPORT, CONTRADICT, or NOT_ENOUGH_INFO), a concise rationale, and the supporting document ID and exact sentence number(s). If no supplied abstract supports or contradicts it, use NOT_ENOUGH_INFO. Do not use outside knowledge.\n\nClaim: " + c["claim"], "materials": [{"path": cand_rel, "sha256": cand_hash, "source_id": "scifact-data-v1"}], "metadata": {"benchmark": "SciFact custom candidate-search subset", "upstream_split": "train", "upstream_claim_id": c["id"], "language": "en", "candidate_count": len(candidates), "task_note": "All tasks share one label-free candidate corpus; evidence documents are present among candidates, but no answers or labels are exposed."}})
        gold.append({"id": tid, "label": label, "evidence": evidence_records, "source_claim_id": c["id"], "source_cited_doc_ids": c.get("cited_doc_ids", [])})

    # Heldout SciFact claims are selected from dev, by source evidence paper,
    # separately from train papers. They use a distinct shared corpus frozen
    # once for the heldout group; development task materials remain unchanged.
    train_papers = {str(d) for c in chosen for d in c.get("cited_doc_ids", [])}
    heldout_claims = []
    used_heldout_papers = set()
    for label in ("SUPPORT", "CONTRADICT", "NOT_ENOUGH_INFO"):
        n = 0
        for c in dev:
            ev = c.get("evidence", {})
            actual = next((r["label"] for rs in ev.values() for r in rs), "NOT_ENOUGH_INFO")
            docs = list(ev) if actual != "NOT_ENOUGH_INFO" else [str(x) for x in c.get("cited_doc_ids", [])]
            if actual != label or len(docs) != 1 or docs[0] in train_papers or docs[0] in used_heldout_papers:
                continue
            heldout_claims.append(c); used_heldout_papers.add(docs[0]); n += 1
            if n == 2: break
    if len(heldout_claims) != 6:
        raise ValueError(f"Could not select 6 paper-disjoint heldout SciFact claims; got {len(heldout_claims)}")
    heldout_docs = [bydoc[d] for d in sorted(used_heldout_papers, key=int)]
    heldout_docs += [r for r in corpus if str(r["doc_id"]) not in used_heldout_papers][:120]
    heldout_rel = "shared/scifact/heldout-candidate-corpus.jsonl"
    heldout_path = root/heldout_rel
    heldout_path.parent.mkdir(parents=True, exist_ok=True)
    heldout_path.write_text("".join(json.dumps({"doc_id": r["doc_id"], "title": r["title"], "abstract": r["abstract"]}, ensure_ascii=False)+"\n" for r in heldout_docs), encoding="utf-8")
    heldout_hash = sha(heldout_path)
    for c in heldout_claims:
        ev=c.get("evidence",{}); ev_gold=[]
        for did,rs in ev.items():
            ev_gold.extend({"doc_id":int(did),"label":r["label"],"sentences":r["sentences"]} for r in rs)
        label=ev_gold[0]["label"] if ev_gold else "NOT_ENOUGH_INFO"
        tid=f"scifact-{int(c['id']):04d}-dev-heldout"
        tasks.append({"id":tid,"kind":"factual-qa","split":"heldout","request":"Using the supplied scientific-abstract candidate corpus, assess the claim. Return exactly one label (SUPPORT, CONTRADICT, or NOT_ENOUGH_INFO), a concise rationale, and the supporting document ID and exact sentence number(s). If no supplied abstract supports or contradicts it, use NOT_ENOUGH_INFO. Do not use outside knowledge.\n\nClaim: "+c["claim"],"materials":[{"path":heldout_rel,"sha256":heldout_hash,"source_id":"scifact-data-v1"}],"metadata":{"benchmark":"SciFact custom candidate-search subset","upstream_split":"dev","upstream_claim_id":c["id"],"language":"en","candidate_count":len(heldout_docs),"task_note":"All heldout tasks share a label-free heldout candidate corpus; cited evidence papers do not overlap development query papers."}})
        gold.append({"id":tid,"label":label,"evidence":ev_gold,"source_claim_id":c["id"],"source_cited_doc_ids":c.get("cited_doc_ids",[])})

    # Chinese reading-comprehension replacement for LongBench. CMRC2018's
    # official project explicitly licenses the dataset CC BY-SA 4.0. Select
    # six distinct contexts from its public train set for development and six
    # from dev for heldout; original question/answer labels remain scoring-only.
    cmrcraw = sources / "cmrc2018" / "raw"
    for upstream_split, split_name, take in (("train", "development", 6), ("dev", "heldout", 6)):
        dataset = json.loads((cmrcraw / f"cmrc2018_{upstream_split}.json").read_text(encoding="utf-8"))
        eligible = [r for r in dataset if r.get("qas") and 700 <= len(r.get("context_text", "")) <= 5000]
        # Deterministic spread through source order, keeping one query per context.
        picks = [eligible[i] for i in range(0, min(len(eligible), take * 20), 20)][:take]
        if len(picks) < take:
            raise ValueError(f"CMRC {upstream_split}: only {len(picks)} eligible rows")
        for i, row in enumerate(picks):
            qa = row["qas"][0]
            tid = f"cmrc2018-{upstream_split}-{i+1:02d}"
            rel = f"tasks/{tid}/materials/context.txt"
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(row["context_text"], encoding="utf-8")
            tasks.append({"id": tid, "kind": "factual-qa", "split": split_name,
                          "request": "请只依据所附中文原文，按JSON返回：answer字段仅填原文中能回答问题的最短答案片段；evidence字段给出支持该片段的原文短引及其上下文位置；limitations字段说明必要限制。若原文无法作答，answer明确写‘原文未提供答案’，并说明原因。不要在answer中加入解释或原文没有的信息。\n\n问题：" + qa["query_text"],
                          "materials": [{"path": rel, "sha256": sha(path), "source_id": "cmrc2018-2018-cc-by-sa-4.0"}],
                          "metadata": {"benchmark": "CMRC2018 custom context QA subset", "upstream_split": upstream_split,
                                       "upstream_context_id": row.get("context_id"), "language": "zh",
                                       "task_note": "One public source question selected per distinct context; this is a small custom subset, not a benchmark-score estimate."}})
            gold.append({"id": tid, "answers": qa.get("answers", []), "source_context_id": row.get("context_id"),
                         "source_query_id": qa.get("query_id"), "source_split": upstream_split})

    # Project source mapping. Raw complete archives remain separate from these
    # bounded task excerpts. FastAPI and Express form development split.
    projects = [
        {"name": "FastAPI", "split": "development", "commit": FASTAPI, "raw": sources/"projects"/"fastapi"/"raw", "stem": "fastapi-"+FASTAPI, "archive": sources/"projects"/"fastapi"/"raw"/f"fastapi-{FASTAPI}.tar.gz", "code": [("fastapi/routing.py", [(397, 524), (1214, 1302)]), ("fastapi/applications.py", [(1207, 1262)])], "docs": ["docs/en/docs/tutorial/path-params.md", "docs/en/docs/tutorial/body.md", "docs/en/docs/tutorial/dependencies/index.md"]},
        {"name": "Express", "split": "development", "commit": EXPRESS, "raw": sources/"projects"/"express"/"raw", "stem": "express-"+EXPRESS, "archive": sources/"projects"/"express"/"raw"/f"express-{EXPRESS}.tar.gz", "code": [("lib/application.js", [(152, 229), (256, 266)]), ("lib/express.js", [(1, 80)])], "docs_root": sources/"projects"/"express-docs"/"raw"/f"expressjs.com-{EXPRESS_DOCS}", "docs": ["src/content/docs/en/5x/guide/routing.mdx", "src/content/docs/en/5x/guide/using-middleware.mdx"]},
        {"name": "Flask", "split": "heldout", "commit": FLASK, "raw": sources/"projects"/"flask"/"raw", "stem": "flask-"+FLASK, "archive": sources/"projects"/"flask"/"raw"/f"flask-{FLASK[:7]}.tar.gz", "code": [("src/flask/app.py", [(966, 1030), (1566, 1607)]), ("src/flask/wrappers.py", [(18, 110)])], "docs": ["docs/lifecycle.rst", "docs/api.rst"]},
        {"name": "Gin", "split": "heldout", "commit": GIN, "raw": sources/"projects"/"gin"/"raw", "stem": "gin-"+GIN, "archive": sources/"projects"/"gin"/"raw"/f"gin-{GIN[:7]}.tar.gz", "code": [("routergroup.go", [(96, 155)]), ("gin.go", [(387, 440), (691, 721)]), ("context.go", [(860, 950)])], "docs": ["README.md"], "doc_ranges": [("docs/doc.md", [(114, 155), (443, 515), (853, 950)])]},
    ]
    prompts = {
        "technical-report": "请用中文撰写一份面向工程师的正式技术报告，概述该项目的HTTP路由、中间件和请求体处理路径。区分文档直接说明与代码推断；重要结论引用给定文件、行号和符号。列出材料范围无法确认的问题，不推断所给范围之外的行为。",
        "design-spec": "请用中文撰写正式设计说明，讨论为单个路由增加请求体大小限制的设计。先陈述材料能确认的当前能力，再提出可选实现方案，明确API位置、优先级、超限行为、流式/解析边界、兼容性和测试策略。所有未由材料证实的行为标为提案；若已有相关能力，指出实际缺口，不得称现有功能不存在。",
    }
    for p in projects:
        src = source_dir(p["raw"], p["stem"], p["archive"])
        docs_root = p.get("docs_root", src)
        for kind in ("technical-report", "design-spec"):
            tid = f"{p['name'].lower()}-{kind}-{'dev' if p['split']=='development' else 'heldout'}"
            mdir = root/"tasks"/tid/"materials"; mdir.mkdir(parents=True, exist_ok=True)
            mats, scope = [], []
            for doc in p["docs"]:
                f = docs_root/doc
                if not f.exists():
                    continue
                rel = f"tasks/{tid}/materials/{Path(doc).name}"
                dst = root/rel; dst.write_bytes(f.read_bytes())
                mats.append({"path": rel, "sha256": sha(dst), "source_id": f"{p['name'].lower()}-docs"})
                scope.append({"upstream_path": doc, "line_range": "full file", "upstream_sha256": sha(f), "material_sha256": sha(dst)})
            # Some repositories have oversized all-in-one manuals; expose only
            # relevant, line-addressed sections and keep omitted context explicit.
            doc_parts = []
            for doc, ranges in p.get("doc_ranges", []):
                f = docs_root/doc
                if not f.exists():
                    continue
                lines = f.read_text(encoding="utf-8").splitlines()
                for start, end in ranges:
                    segment = lines[start-1:end]
                    doc_parts.append(f"\n## {doc}:{start}-{start+len(segment)-1}\n")
                    doc_parts.extend(f"{n}: {line}\n" for n, line in enumerate(segment, start))
                    scope.append({"upstream_path": doc, "line_range": f"{start}-{start+len(segment)-1}", "upstream_sha256": sha(f), "excerpt_sha256": hashlib.sha256(("\n".join(segment)+"\n").encode()).hexdigest()})
            if doc_parts:
                rel=f"tasks/{tid}/materials/docs-excerpts.md"; dp=root/rel
                dp.write_text(f"# {p['name']} documentation excerpts\n# Line numbers are upstream 1-based; omitted sections may affect interpretation.\n"+"".join(doc_parts),encoding="utf-8")
                mats.append({"path":rel,"sha256":sha(dp),"source_id":f"{p['name'].lower()}-docs"})
            blocks = [f"# {p['name']} source excerpts at commit {p['commit']}\n", "# Line numbers are upstream 1-based. Full source archive retained separately.\n"]
            for relup, ranges in p["code"]:
                f = src/relup
                if not f.exists(): continue
                lines = f.read_text(encoding="utf-8").splitlines()
                for start, end in ranges:
                    segment = lines[start-1:end]
                    blocks.append(f"\n## {relup}:{start}-{start+len(segment)-1}\n")
                    blocks.extend(f"{n}: {line}\n" for n, line in enumerate(segment,start))
                    scope.append({"upstream_path": relup, "line_range": f"{start}-{start+len(segment)-1}", "upstream_sha256": sha(f), "excerpt_sha256": hashlib.sha256(("\n".join(segment)+"\n").encode()).hexdigest()})
            c_rel=f"tasks/{tid}/materials/code-excerpts.md"; cp=root/c_rel; cp.write_text("".join(blocks), encoding="utf-8")
            mats.append({"path":c_rel,"sha256":sha(cp),"source_id":f"{p['name'].lower()}-code"})
            task={"id":tid,"kind":kind,"split":p["split"],"request":prompts[kind],"materials":mats,"metadata":{"project":p["name"],"upstream_commit":p["commit"],"language":"zh","material_scope":scope,"limitations":"Only listed documentation files and code line ranges are provided. Full upstream archives remain in the provenance area; omissions may change interpretation. No claim is made beyond the supplied scope."}}
            tasks.append(task)
            # Checklist is source-derived and intentionally not represented as
            # expert gold; evaluator criteria require later human calibration.
            gold.append({"id":tid,"rubric_status":"unreviewed source-derived checklist","criteria":["Claims accurately distinguish documented behavior from code inference.","Important conclusions cite supplied source file and line or named section.","Scope gaps and limitations are stated without extrapolating omitted code.","Output is professional Chinese prose organized for the requested document type.","Design recommendations identify compatibility and test implications; proposals are not stated as current implementation."]})

    # Development view only; hidden heldout tasks are kept out of this file.
    development = [t for t in tasks if t["split"] == "development"]
    write_json(root / "tasks.jsonl", tasks)  # JSONL corrected below
    (root/"tasks.jsonl").write_text("".join(json.dumps(t,ensure_ascii=False)+"\n" for t in tasks),encoding="utf-8")
    (root/"formal-v1-development.jsonl").write_text("".join(json.dumps(t,ensure_ascii=False)+"\n" for t in development),encoding="utf-8")
    scoring.mkdir(parents=True,exist_ok=True)
    (scoring/"gold.jsonl").write_text("".join(json.dumps(g,ensure_ascii=False)+"\n" for g in gold),encoding="utf-8")
    split_by_id={t["id"]:t["split"] for t in tasks}
    for split_name, filename in (("development","development-gold.jsonl"),("heldout","heldout-gold.jsonl")):
        rows=[g for g in gold if split_by_id.get(g["id"])==split_name]
        (scoring/filename).write_text("".join(json.dumps(g,ensure_ascii=False)+"\n" for g in rows),encoding="utf-8")
    print(json.dumps({"tasks":len(tasks),"development":len(development),"heldout":len(tasks)-len(development),"gold":len(gold),"candidate_corpus_sha256":cand_hash},ensure_ascii=False))


if __name__ == "__main__":
    main()
