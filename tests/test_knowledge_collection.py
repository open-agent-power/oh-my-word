import sys

import pytest

pytest.importorskip("bs4")  # optional public-collection helper; core KB is stdlib
from tools.knowledge_sources import collect_ip_sources as collect


def test_patent_extract_preserves_actual_prose_and_excludes_navigation():
    raw = b'''<html><body><h1>Navigation only</h1><p>CPC repeated tags</p>
      <section itemprop="abstract"><div itemprop="content">Actual abstract</div></section>
      <section itemprop="description"><div itemprop="content">Full description sentence</div></section>
      <section itemprop="claims"><div itemprop="content">1. Actual independent claim</div></section>
    </body></html>'''
    text = collect.clean_html(raw, "cn103597488a-information-security-system-and-method")
    assert "Full description sentence" in text and "1. Actual independent claim" in text
    assert "Navigation only" not in text and "CPC repeated tags" not in text


def test_collector_rejects_existing_output_before_network(tmp_path, monkeypatch):
    target = tmp_path / "existing"
    target.mkdir()
    marker = target / "owner.txt"
    marker.write_text("preserve", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["collect", "--out", str(target)])
    monkeypatch.setattr(collect, "fetch", lambda _: pytest.fail("Network must not start"))
    with pytest.raises(ValueError, match="fresh"):
        collect.main()
    assert marker.read_text(encoding="utf-8") == "preserve"


def test_regulation_shell_cannot_become_a_full_legal_source():
    with pytest.raises(ValueError, match="navigation shell"):
        collect.clean_html(b"<main><p>Long navigation menu without legal body</p></main>", "computer-software-protection-regulations-consolidated")
