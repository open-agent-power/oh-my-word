#!/usr/bin/env python3
"""Collect a small, fixed-index source pack of public Chinese IP materials.

Downloads source pages as raw HTML/PDF, extracts readable article text, records
hashes and retrieval metadata, and writes a manifest for deterministic indexing.
This is an archival helper, not a legal-status checker.
"""
from __future__ import annotations

import argparse
import hashlib
import gzip
import json
import re
import subprocess
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup

UA = "ip-knowledge-source-collector/1.0 (public-source archival)"

SOURCES = [
    {"id":"computer-software-copyright-registration-measures","title":"计算机软件著作权登记办法","url":"https://www.ncac.gov.cn/xxfb/flfg/bmgz/202410/t20241015_869486.html","kind":"rule","topics":["copyright"],"revision":"国家版权局令第1号；2002-02-20公布并施行","effective_from":"2002-02-20"},
    {"id":"computer-software-protection-regulations-consolidated","title":"计算机软件保护条例（历次修订文本）","url":"https://xzfg.moj.gov.cn/front/law/detail?LawID=581","kind":"rule","topics":["copyright"],"revision":"司法部国家行政法规库所载文本；页面列出2001年公布、2011年第一次修订、2013年第二次修订；最近修订施行日按2013年决定记为2013-03-01","effective_from":"2013-03-01"},
    {"id":"patent-law-2020","title":"中华人民共和国专利法（2020年修正）","url":"https://www.cnipa.gov.cn/art/2020/11/23/art_97_155167.html","kind":"rule","topics":["patent"],"revision":"2020年修正；2021-06-01施行","effective_from":"2021-06-01"},
    {"id":"patent-law-implementing-regulations-2023","title":"中华人民共和国专利法实施细则（2023年修订）","url":"https://www.cnipa.gov.cn/art/2023/12/21/art_98_189197.html","kind":"rule","topics":["patent"],"revision":"2023年修订；国务院令第769号","effective_from":"2024-01-20"},
    {"id":"patent-examination-guidelines-2025-revision","title":"专利审查指南（2023版，2025年修订）","url":"https://www.cnipa.gov.cn/module/download/downfile.jsp?classid=0&showname=%E4%B8%93%E5%88%A9%E5%AE%A1%E6%9F%A5%E6%8C%87%E5%8D%972023%EF%BC%882025%E5%B9%B4%E4%BF%AE%E8%AE%A2%EF%BC%89.pdf&filename=3f6306029ff741dfad6cee9282ec6efc.pdf","kind":"rule","document_type":"examination_guideline","topics":["patent"],"revision":"官方PDF标题为2023版（2025年修订）；PDF页面未说明单独生效日；84号修订另于2026-01-01施行"},
    {"id":"patent-examination-guidelines-amendment-order-84","title":"国家知识产权局关于修改《专利审查指南》的决定（局令第84号）","url":"https://www.cnipa.gov.cn/art/2025/11/14/art_99_202568.html","kind":"rule","topics":["patent"],"revision":"局令第84号；决定自2026-01-01施行","effective_from":"2026-01-01"},
    {"id":"cn103597488a-information-security-system-and-method","title":"信息安全系统和方法（CN103597488A）","url":"https://patents.google.com/patent/CN103597488A/zh","kind":"reference","topics":["patent"],"revision":"公开文本 CN103597488A；公开日2014-02-19；Google Patents 中国文本页","use_role":"prior_art_or_writing_reference","rights_note":"第三方专利全文镜像；保留原始公开文本供检索和写作结构参考，不代表本项目技术事实、可专利性结论或法律意见。"},
]

def fetch(url: str) -> tuple[bytes, str, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read(), resp.headers.get("Content-Type", ""), resp.geturl()
    except Exception:
        # A few government sites negotiate an EC point urllib/OpenSSL rejects;
        # use the OS curl TLS stack as a verified fallback on Windows.
        if sys.platform != "win32": raise
        with tempfile.NamedTemporaryFile(delete=False) as tmp: name=tmp.name
        try:
            proc=subprocess.run(["curl.exe","-L","--fail","--silent","--show-error","--connect-timeout","15","--max-time","60","-A",UA,"-D","-",url,"-o",name],capture_output=True,check=True,timeout=75)
            raw=Path(name).read_bytes()
            headers=proc.stdout.decode("latin1","replace").split("\r\n")
            ctype=next((h.split(":",1)[1].strip() for h in headers if h.lower().startswith("content-type:")),"")
            return raw,ctype,url
        finally:
            try: Path(name).unlink()
            except FileNotFoundError: pass

def clean_html(raw: bytes, source_id: str) -> str:
    soup = BeautifulSoup(raw, "html.parser")
    for el in soup.select("script,style,nav,header,footer,aside,form,iframe,svg,noscript"):
        el.decompose()
    if source_id == "cn103597488a-information-security-system-and-method":
        lines = ["# 信息安全系统和方法（CN103597488A）", "", "Source URL: " + SOURCES_BY_ID[source_id]["url"], "",
                 "公开文本，图形及当前法律状态未核查；不是本案事实。", ""]
        for prop in ("abstract", "description", "claims"):
            section = soup.find("section", attrs={"itemprop": prop})
            content = section.find(attrs={"itemprop": "content"}) if section else None
            if content is None:
                raise ValueError("Missing actual patent section: " + prop)
            lines += ["## " + prop, "", content.get_text("\n", strip=True), ""]
        return "\n".join(lines).strip() + "\n"
    candidates = ["article", "#zoom", ".TRS_Editor", ".article-content", ".content", ".view TRS_Editor", ".law-chapter", "main", "patent-section"]
    node = next((soup.select_one(s) for s in candidates if soup.select_one(s)), None)
    if node is None:
        node = soup.body or soup
    title = soup.title.get_text(" ", strip=True) if soup.title else source_id
    lines = [f"# {title}", "", f"Source URL: {SOURCES_BY_ID[source_id]['url']}", "", "Extraction: page article/content region; navigation and boilerplate removed.", ""]
    for el in node.find_all(["h1","h2","h3","h4","p","li","tr"]):
        t = re.sub(r"\s+", " ", el.get_text(" ", strip=True))
        if not t or len(t) < 2: continue
        if el.name.startswith("h"): lines += ["## " + t, ""]
        else: lines += [t, ""]
    text = "\n".join(lines).strip() + "\n"
    if source_id == "computer-software-protection-regulations-consolidated" and not all(term in text for term in ("第一次修订", "第二次修订", "第三十三条")):
        raise ValueError("Official regulation body not extracted; do not index a navigation shell")
    return text

SOURCES_BY_ID = {s["id"]:s for s in SOURCES}

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True, help="fresh destination folder; prior source packs are preserved")
    ap.add_argument("--only", action="append", help="collect only this source id; repeatable")
    args = ap.parse_args()
    out = args.out.resolve()
    if out.exists():
        raise ValueError("Output exists; use a fresh version directory")
    (out/"documents").mkdir(parents=True); (out/"raw").mkdir()
    docs = []
    for src in SOURCES:
        if args.only and src["id"] not in args.only: continue
        raw, ctype, final_url = fetch(src["url"])
        decoded = gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw
        ext = ".pdf" if "pdf" in ctype.lower() or decoded[:4] == b"%PDF" else ".html"
        raw_path = out/"raw"/(src["id"]+ext); raw_path.write_bytes(decoded)
        if ext == ".pdf":
            import fitz
            pdf = fitz.open(stream=decoded, filetype="pdf")
            body = "\n\n".join(f"## Page {i+1}\n\n{page.get_text('text').strip()}" for i,page in enumerate(pdf))
            text = f"# {src['title']}\n\nSource URL: {src['url']}\n\nExtraction: full PDF text layer via PyMuPDF; {len(pdf)} pages.\n\n{body}\n"
        else:
            text = clean_html(decoded, src["id"])
        if len(text.strip()) < 1000: raise RuntimeError(f"Suspiciously short extraction for {src['id']}: {len(text)} chars")
        dest = out/"documents"/(src["id"]+".md"); dest.write_text(text, encoding="utf-8")
        item = {k:v for k,v in src.items() if k not in ("url",)}
        item.update({"path":"documents/"+dest.name,"sha256":hashlib.sha256(dest.read_bytes()).hexdigest(),"url":src["url"],"source_final_url":final_url,"source_content_type":ctype,"raw_path":"raw/"+raw_path.name,"raw_sha256":hashlib.sha256(raw_path.read_bytes()).hexdigest(),"retrieved_at":datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z"),"extraction":"full page article text or PDF text layer; see raw/ for original HTML/PDF response body"})
        docs.append(item)
        print(f"{src['id']}: {len(text)} chars; raw={len(raw)} bytes; {final_url}")
    manifest_path = out/"manifest.json"
    manifest={"schema_version":1,"name":"cn-ip-writing-20261021","domain":"copyright-patent","documents":docs}
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"Wrote {manifest_path} ({len(docs)} documents)")
    return 0

if __name__ == "__main__":
    try: sys.exit(main())
    except Exception as e: print(f"collect failed: {e}",file=sys.stderr); sys.exit(1)
