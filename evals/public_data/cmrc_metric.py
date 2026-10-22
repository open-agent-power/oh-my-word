"""Independent CMRC-style EM/F1 implementation for the frozen evaluation.

This module independently implements the published CMRC2018 evaluation
protocol: punctuation-insensitive exact match and mixed Chinese/English
character/token segmentation followed by longest-common-subsequence F1, with
the best reference answer used for each question. The protocol is documented
in Yiming Cui et al., "A Span-Extraction Dataset for Chinese Machine Reading
Comprehension" (EMNLP-IJCNLP 2019), and in the public CMRC2018 v5 scorer at
https://github.com/ymcui/cmrc2018/blob/c0eb1b6ba219847457e6af3180da722bbeb656af/data/cmrc2018_evaluate.py.

This is not a port or distribution of the upstream script. The upstream repo's
CC BY-SA 4.0 notice is preserved for the dataset, but no separate code license
for that script is assumed here. NLTK is used when available; the stdlib Latin
tokenizer fallback may differ on English contractions/abbreviations.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable, Mapping


SP_CHAR = set("-:_*^/\\~`+=，。：？！“”；’《》……·、「」（）－～『』")
CN_CHAR = re.compile(r"[\u4e00-\u9fa5]")
BOUNDARIES = re.compile(r"([\u4e00-\u9fa5" + re.escape("".join(SP_CHAR)) + r"])" )
try:
    from nltk import word_tokenize as _nltk_word_tokenize
except ImportError:
    _nltk_word_tokenize = None


def _word_tokenize(text: str) -> list[str]:
    if _nltk_word_tokenize is not None:
        try:
            return _nltk_word_tokenize(text)
        except LookupError:
            pass
    return re.findall(r"[A-Za-z0-9]+(?:['’][A-Za-z0-9]+)*|[^\w\s]", text, flags=re.UNICODE)


def mixed_segmentation(text: str, rm_punc: bool = False) -> list[str]:
    text = str(text).casefold().strip()
    out: list[str] = []
    # Segment around Chinese characters and listed punctuation first, then
    # tokenize intervening Latin runs. This is an independent implementation
    # of the public scoring rule, rather than a transliteration of its loop.
    for piece in (p for p in BOUNDARIES.split(text) if p):
        if CN_CHAR.fullmatch(piece) or piece in SP_CHAR:
            if not (rm_punc and piece in SP_CHAR):
                out.append(piece)
        else:
            out.extend(_word_tokenize(piece))
    return out


def remove_punctuation(text: str) -> str:
    text = str(text).casefold().strip()
    return "".join(ch for ch in text if ch not in SP_CHAR)


def lcs_length(a: list[str], b: list[str]) -> int:
    # Equivalent dynamic-programming LCS length to upstream find_lcs; rolling
    # rows avoid the quadratic memory allocation in the original script.
    prev = [0] * (len(b) + 1)
    for x in a:
        curr = [0]
        for j, y in enumerate(b, 1):
            curr.append(prev[j - 1] + 1 if x == y else max(prev[j], curr[-1]))
        prev = curr
    return prev[-1]


def calc_em_score(answers: Iterable[str], prediction: str) -> int:
    p = remove_punctuation(prediction)
    return int(any(remove_punctuation(a) == p for a in answers))


def calc_f1_score(answers: Iterable[str], prediction: str) -> float:
    pred = mixed_segmentation(prediction, rm_punc=True)
    best = 0.0
    for answer in answers:
        ref = mixed_segmentation(answer, rm_punc=True)
        common = lcs_length(ref, pred)
        if common == 0:
            continue
        precision = common / len(pred)
        recall = common / len(ref)
        best = max(best, 2 * precision * recall / (precision + recall))
    return best


def evaluate_rows(rows: Iterable[dict], predictions: Mapping[str, str]) -> dict:
    total = skipped = em = 0
    f1 = 0.0
    for context in rows:
        for qa in context["qas"]:
            total += 1
            qid = qa["query_id"].strip()
            if qid not in predictions:
                skipped += 1
                continue
            answer = str(predictions[qid])
            refs = qa["answers"]
            em += calc_em_score(refs, answer)
            f1 += calc_f1_score(refs, answer)
    denom = total or 1
    em_pct, f1_pct = 100.0 * em / denom, 100.0 * f1 / denom
    return {"EM": em_pct, "F1": f1_pct, "AVERAGE": (em_pct + f1_pct) / 2,
            "TOTAL": total, "SKIP": skipped,
            "english_tokenizer": "nltk.word_tokenize" if _nltk_word_tokenize else "stdlib regex fallback"}


def evaluate_files(dataset_path: Path, prediction_path: Path) -> dict:
    rows = json.loads(dataset_path.read_text(encoding="utf-8"))
    predictions = json.loads(prediction_path.read_text(encoding="utf-8"))
    return evaluate_rows(rows, predictions)


def evaluate_subset(gold_rows: Iterable[dict], predictions: Mapping[str, str]) -> dict:
    """Score custom task rows from `development-gold.jsonl` or heldout gold.

    Prediction keys are task IDs and values are the extracted `answer` field.
    This uses only selected items as the denominator, while retaining the
    official CMRC max-reference EM and LCS-F1 calculation.
    """
    total = skipped = em = 0
    f1 = 0.0
    for row in gold_rows:
        total += 1
        tid = row["id"]
        if tid not in predictions:
            skipped += 1
            continue
        refs = row["answers"]
        answer = str(predictions[tid])
        em += calc_em_score(refs, answer)
        f1 += calc_f1_score(refs, answer)
    denom=total or 1
    em_pct, f1_pct = 100.0*em/denom, 100.0*f1/denom
    return {"EM":em_pct,"F1":f1_pct,"AVERAGE":(em_pct+f1_pct)/2,
            "TOTAL":total,"SKIP":skipped,
            "english_tokenizer":"nltk.word_tokenize" if _nltk_word_tokenize else "stdlib regex fallback"}
