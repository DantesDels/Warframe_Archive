"""Regression tests for live-scrape hardening fixes (thread safety, search, UX)."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from warframe_lore.v1.scraper.adapters.outbound.connectors.html import HtmlConnector
from warframe_lore.v1.scraper.adapters.outbound.connectors.mediawiki import (
    MediaWikiConnector,
)
from warframe_lore.v1.scraper.adapters.outbound.connectors.rest import RestConnector
from warframe_lore.v1.scraper.adapters.outbound.persistence.event_log import (
    JsonlEventLogAdapter,
)
from warframe_lore.v1.scraper.observability.progress import ProgressReporter
from warframe_lore.v1.scraper.ports.outbound.sources import ConnectorContext
from warframe_lore.v1.scraper.use_cases.universe_run_helpers import active_sources


def test_event_log_is_thread_safe_under_concurrent_writes(tmp_path: Path) -> None:
    log_path = tmp_path / "events.jsonl"
    adapter = JsonlEventLogAdapter(log_path)

    def worker(wid: int) -> None:
        for i in range(40):
            adapter.emit("fetch_ok", worker=wid, seq=i, url=f"https://ex/{wid}/{i}")

    threads = [threading.Thread(target=worker, args=(w,)) for w in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    lines = [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln]
    assert len(lines) == 240
    parsed = [json.loads(ln) for ln in lines]
    assert all(item["type"] == "fetch_ok" for item in parsed)


def test_mediawiki_respects_srsearch_query_parameter() -> None:
    calls: list[dict[str, Any]] = []

    class FakeClient:
        def get(self, url: str, *, params: dict[str, Any] | None = None, **_kw: Any):
            p = dict(params or {})
            calls.append(p)
            if p.get("meta") == "siteinfo":
                payload = {"query": {"general": {"mainpage": "Main Page"}}}
            elif p.get("list") == "search":
                payload = {"query": {"search": [{"title": "Starfall Chronicles"}]}}
            elif p.get("prop") == "info":
                payload = {"query": {"pages": {"1": {"title": "Starfall Chronicles"}}}}
            else:
                payload = {
                    "query": {
                        "pages": {
                            "1": {
                                "title": "Starfall Chronicles",
                                "fullurl": "https://en.wikipedia.org/wiki/Starfall",
                                "extract": "Starfall Chronicles is a sci-fi epic.",
                            }
                        }
                    }
                }
            return SimpleNamespace(content=json.dumps(payload).encode("utf-8"))

    src = {
        "id": "s-wiki",
        "kind": "wiki",
        "location": (
            "https://en.wikipedia.org/w/api.php"
            "?action=query&list=search&srsearch=Starfall&format=json"
        ),
    }
    ctx = ConnectorContext(client=FakeClient(), limits={"max_pages_per_source": 5})
    pages = MediaWikiConnector().collect(src, ctx)
    has_search = any(
        c.get("list") == "search" and c.get("srsearch") == "Starfall" for c in calls
    )
    assert has_search
    assert not any(c.get("titles") == "Main Page" for c in calls)
    assert pages and pages[0].title == "Starfall Chronicles"


def test_html_root_error_is_surfaced_not_swallowed() -> None:
    class FailingClient:
        def get(self, *_a: Any, **_kw: Any):
            raise RuntimeError("403 Forbidden")

    src = {"id": "s-403", "kind": "website", "location": "https://forums.example/"}
    ctx = ConnectorContext(client=FailingClient(), limits={"max_pages_per_source": 2})
    with pytest.raises(RuntimeError, match="403 Forbidden"):
        HtmlConnector().collect(src, ctx)


def test_rest_connector_uses_resource_name_instead_of_item_zero() -> None:
    class FakeClient:
        def get(self, *_a: Any, **_kw: Any):
            return SimpleNamespace(
                content=json.dumps({"prices": [1, 2, 3]}).encode("utf-8"),
                headers={},
            )

    src = {"id": "s-json", "kind": "api", "location": "https://cdn.ex/weeklyStats.json"}
    ctx = ConnectorContext(client=FakeClient(), limits={"max_pages_per_source": 5})
    pages = RestConnector().collect(src, ctx)
    assert len(pages) == 1
    assert pages[0].title == "weeklyStats.json"


def test_active_sources_deduplicates_duplicate_urls() -> None:
    snap = SimpleNamespace(
        sources_by_uid={
            "u1": [
                {"id": "s1", "status": "approved", "location": "https://ex.org/en"},
                {"id": "s2", "status": "approved", "location": "https://ex.org/en/"},
                {"id": "s3", "status": "approved", "location": "https://ex.org/fr"},
            ]
        }
    )
    ctx = SimpleNamespace(snapshot=snap)
    out = active_sources(ctx, "u1")  # type: ignore[arg-type]
    assert [s["id"] for s in out] == ["s1", "s3"]


def test_progress_reporter_percent_is_strictly_monotonic() -> None:
    seen: list[int] = []
    rep = ProgressReporter(lambda ev: seen.append(ev.percent))
    rep.source(8, 10, "https://ex.org/8")
    rep.source(3, 10, "https://ex.org/3")
    rep.source(10, 10, "https://ex.org/10")
    assert seen == sorted(seen)
    assert seen[1] >= seen[0]


def test_playwright_build_page_and_mediawiki_cdn_exclusion() -> None:
    from warframe_lore.v1.scraper.adapters.outbound.connectors.playwright import (
        PlaywrightConnector,
        _build_page,
    )

    page = _build_page(
        "https://example.org/hero",
        "Hero Page",
        "<html><body><h1>Hero Page</h1><p>Body lore text here.</p></body></html>",
    )
    assert page.title == "Hero Page"
    assert isinstance(page.metadata["sections"], list)

    class StaticClient:
        def get(self, url: str, **_kw: Any):
            html = (
                "<html><head><title>Atlas</title></head><body><main>"
                + ("Ancient lore archive content. " * 20)
                + "</main></body></html>"
            )
            return SimpleNamespace(url=url, encoding="utf-8", content=html.encode())

    p_ctx = ConnectorContext(
        client=StaticClient(),
        limits={"use_playwright": True, "max_pages_per_source": 1},
    )
    pages = PlaywrightConnector().collect(
        {"id": "s-p", "kind": "website", "location": "https://example.org/atlas"}, p_ctx
    )
    assert len(pages) == 1 and pages[0].title == "Atlas"

    mw = MediaWikiConnector()
    ctx = ConnectorContext(client=None, limits={})
    assert mw.can_handle({"location": "https://images.wikia.com/a.png"}, ctx) is False
    assert mw.can_handle({"location": "https://img.wikia.nocookie.net/x"}, ctx) is False
    assert mw.can_handle({"location": "https://wiki.example.org/w/A"}, ctx) is True
