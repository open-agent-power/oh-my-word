"""Freeze selected real workspace files as project evidence, without networking."""
from pathlib import Path
import argparse
import shutil
from datetime import datetime, timezone

from word_skills.common import sha256, write_json


def prepare(repo, output):
    repo, output = Path(repo).resolve(), Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    documents = []
    for relative in ("word_skills/knowledge.py", "word_skills/knowledge_context.py", "pyproject.toml"):
        source = repo / relative
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        assert sha256(source) == sha256(target)
        documents.append({"id": relative.replace("/", "-").replace(".", "-"), "title": relative,
            "path": relative, "sha256": sha256(target), "url": "local://word-skills-working-tree/" + relative,
            "kind": "project", "topics": ["copyright", "patent"],
            "revision": "working-tree-sha256:" + sha256(source),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "original_workspace_path": str(source), "rights_note": "本地项目文件快照，不推断权属、发明人或性能实测。"})
    shutil.copyfile(repo / "LICENSE", output / "LICENSE")
    write_json(output / "manifest.json", {"schema_version": 1, "name": "word-skills-project-evidence",
        "domain": "copyright-patent", "scope": "real implementation subset, not entire software deposit or novel invention claim", "documents": documents})
    return output / "manifest.json"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(prepare(args.repo, args.out))
