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


def test_10k_pending_children_capped_offloaded_and_error_summary(
    tmp_path: Path,
) -> None:
    from warframe_lore.v1.scraper.use_cases.error_summary import summarize_run_errors
    from warframe_lore.v1.scraper.use_cases.pending_children_store import (
        MAX_PENDING_CHILDREN_PER_RUN,
        MAX_PENDING_CHILDREN_PER_SOURCE,
        cap_and_dedupe_pending,
        offload_pending_children,
    )

    errors = (
        [f"https://example.org/a/{i}: HTTP 403 Forbidden" for i in range(80)]
        + [f"https://example.org/b/{i}: HTTP 429 Too Many Requests" for i in range(40)]
        + [f"https://example.org/c/{i}: Timeout after 15s" for i in range(65)]
        + [f"https://example.org/d/{i}: HTTP 404 Not Found" for i in range(48)]
    )
    summary = summarize_run_errors(errors)
    assert summary == "Erreurs : 120x HTTP 403/429, 65x Timeout, 48x HTTP 404"

    raw_per_source = [
        {"url": f"https://example.org/child/{i % 250}", "parent": "https://example.org"}
        for i in range(400)
    ]
    per_source = cap_and_dedupe_pending(raw_per_source)
    assert len(per_source) == MAX_PENDING_CHILDREN_PER_SOURCE

    massive_pending = [
        {
            "url": f"https://warframe.com/child/{i}",
            "parent": "https://www.warframe.com/en",
        }
        for i in range(12_000)
    ]
    kept, total_unique, jsonl_path = offload_pending_children(
        tmp_path, "warframe", massive_pending
    )
    assert len(kept) == MAX_PENDING_CHILDREN_PER_RUN
    assert total_unique == 12_000
    assert jsonl_path is not None and jsonl_path.is_file()
    assert jsonl_path == tmp_path / "pending_children" / "warframe.jsonl"
    lines = jsonl_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 12_000


def test_post_run_10k_children_ui_apply_fast_and_synchronized(
    tmp_path: Path,
) -> None:
    import time

    from PySide6.QtWidgets import QApplication, QTabWidget

    from warframe_lore.v1.scraper.UI.app import AtelierApp
    from warframe_lore.v1.scraper.UI.runtime.snapshot import snapshot
    from warframe_lore.v1.scraper.UI.runtime.worker_support import (
        merge_result_in_worker,
    )
    from warframe_lore.v1.scraper.UI.views.simple_table import (
        MAX_VISIBLE_ROWS,
        SimpleTable,
    )

    _ = QApplication.instance() or QApplication([])
    data_path = tmp_path / "workspace.json"
    app = AtelierApp(data_path=data_path)
    uni = app.workspace.create("Warframe")
    uid = str(uni["id"])
    app.refresh(uid)

    export_dir = tmp_path / "exports" / uid / "run-large"
    export_dir.mkdir(parents=True, exist_ok=True)
    (export_dir / "manifest.json").write_text(
        '{"document_count": 422}', encoding="utf-8"
    )

    snap = snapshot(app.workspace)
    docs = [
        {
            "id": f"doc-{i}",
            "universeId": uid,
            "url": f"https://www.warframe.com/en/news/{i}",
            "title": f"Archive Lore {i}",
            "docType": "lore",
            "language": "fr",
            "content": "Texte lore Warframe. " * 20,
            "contentHash": f"hash-{i}",
            "relevance": 0.92,
        }
        for i in range(422)
    ]
    pending = [
        {
            "url": f"https://www.warframe.com/en/child-{i}",
            "parent": "https://www.warframe.com/en",
        }
        for i in range(10_500)
    ]
    result: dict[str, Any] = {
        "ok": True,
        "runs": [
            {
                "universeId": uid,
                "docs": docs,
                "pending_children": pending,
                "run": {
                    "id": "run-large",
                    "universeIds": [uid],
                    "status": "completed",
                    "startedAt": "2026-04-20T12:00:00Z",
                    "counts": {"emitted": 422, "errors": 233},
                },
            }
        ],
    }

    # Background worker thread performs merge, blob compaction, JSONL offload and save
    merge_result_in_worker(snap, result)
    assert "merged_workspace_data" in result
    assert (tmp_path / "pending_children" / f"{uid}.jsonl").is_file()

    # Main thread only swaps state and refreshes UI widgets quickly
    t0 = time.perf_counter()
    app._on_execution_finished(result)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    assert elapsed_ms < 500.0
    assert app.status_bar.currentMessage() == "Statut : Prêt"
    assert len(app.workspace.documents_for(uid)) == 422
    assert len(app.workspace.runs_for(uid)) == 1
    assert len(app.workspace.candidates_for(uid)) == 1000

    tabs = app.details.findChild(QTabWidget)
    assert tabs is not None
    tab_titles = [tabs.tabText(i) for i in range(tabs.count())]
    assert "Documents (422)" in tab_titles
    assert "Exécutions (1)" in tab_titles
    assert "Candidats (1000)" in tab_titles
    assert "Data" in tab_titles

    # Verify Qt table models cap visible QStandardItem rows at MAX_VISIBLE_ROWS (500)
    for table in app.details.findChildren(SimpleTable):
        assert table.model_data.rowCount() <= MAX_VISIBLE_ROWS

    app.close()
    app.deleteLater()


def test_multilingual_url_filtering_and_candidate_language_selector(
    tmp_path: Path,
) -> None:
    from PySide6.QtWidgets import QApplication, QCheckBox, QPushButton

    from warframe_lore.v1.scraper.collect.language import (
        canonical_locale_url_key,
        detect_url_locale,
        is_url_language_allowed,
    )
    from warframe_lore.v1.scraper.collect.language_purge import (
        purge_disallowed_languages_and_duplicates,
    )
    from warframe_lore.v1.scraper.UI.views.candidates.view import candidates_view
    from warframe_lore.v1.scraper.UI.views.simple_table import SimpleTable
    from warframe_lore.v1.scraper.UI.workspace import WorkshopWorkspace

    assert detect_url_locale("https://www.warframe.com/en/news/lotus") == "en"
    assert detect_url_locale("https://www.warframe.com/fr/news/lotus") == "fr"
    assert detect_url_locale("https://www.warframe.com/zh-hans/news/lotus") == "zh"
    assert detect_url_locale("https://www.warframe.com/pt-br/news/lotus") == "pt"
    assert detect_url_locale("https://fr.wiki.warframe.com/w/Excalibur") == "fr"
    assert detect_url_locale("https://support.warframe.com/hc/de/articles/1") == "de"
    assert detect_url_locale("https://consumer-redress.ec.europa.eu/site_hu") == "hu"
    assert detect_url_locale("https://wiki.warframe.com/w/Excalibur") is None

    # Default ('en',) keeps English & unprefixed URLs, rejects all other locales
    assert is_url_language_allowed("https://www.warframe.com/en/news/lotus") is True
    assert is_url_language_allowed("https://wiki.warframe.com/w/Excalibur") is True
    for foreign in (
        "https://www.warframe.com/fr/news/lotus",
        "https://www.warframe.com/de/news/lotus",
        "https://www.warframe.com/es/news/lotus",
        "https://www.warframe.com/pt-br/news/lotus",
        "https://www.warframe.com/ru/news/lotus",
        "https://www.warframe.com/ja/news/lotus",
        "https://www.warframe.com/ko/news/lotus",
        "https://www.warframe.com/zh-hans/news/lotus",
        "https://www.warframe.com/zh-hant/news/lotus",
        "https://www.warframe.com/pl/news/lotus",
        "https://www.warframe.com/tr/news/lotus",
        "https://www.warframe.com/uk/news/lotus",
        "https://www.warframe.com/th/news/lotus",
        "https://fr.wiki.warframe.com/w/Excalibur",
    ):
        assert is_url_language_allowed(foreign, ("en",)) is False

    # Canonical key strips locale prefix so translated siblings deduplicate
    k_en = canonical_locale_url_key("https://www.warframe.com/en/news/lotus")
    k_fr = canonical_locale_url_key("https://www.warframe.com/fr/news/lotus")
    k_bare = canonical_locale_url_key("https://www.warframe.com/news/lotus")
    assert k_en == k_fr == k_bare == "warframe.com/news/lotus"

    _ = QApplication.instance() or QApplication([])
    ws = WorkshopWorkspace(path=tmp_path / "workspace.json")
    uni = ws.create("Warframe")
    uid = str(uni["id"])
    ws.add_manual_source(uid, "https://www.warframe.com/en")
    ws.data["candidates"] = [
        {
            "id": "c-en",
            "universeId": uid,
            "kind": "website",
            "location": "https://www.warframe.com/en/news/update-40",
            "title": "Update 40 EN",
            "score": 0.9,
            "status": "proposed",
            "discoveredBy": "manifest_review",
            "proof": "test",
        },
        {
            "id": "c-fr",
            "universeId": uid,
            "kind": "website",
            "location": "https://www.warframe.com/fr/news/update-40",
            "title": "Update 40 FR",
            "score": 0.9,
            "status": "proposed",
            "discoveredBy": "manifest_review",
            "proof": "test",
        },
        {
            "id": "c-de",
            "universeId": uid,
            "kind": "website",
            "location": "https://www.warframe.com/de/news/update-40",
            "title": "Update 40 DE",
            "score": 0.9,
            "status": "proposed",
            "discoveredBy": "manifest_review",
            "proof": "test",
        },
        {
            "id": "c-ru",
            "universeId": uid,
            "kind": "website",
            "location": "https://www.warframe.com/ru/news/other",
            "title": "Other RU",
            "score": 0.9,
            "status": "proposed",
            "discoveredBy": "manifest_review",
            "proof": "test",
        },
    ]

    widget = candidates_view(ws, uni, lambda: None)
    table = widget.findChild(SimpleTable)
    cb_en = widget.findChild(QCheckBox, "CandidateLang_en")
    cb_fr = widget.findChild(QCheckBox, "CandidateLang_fr")
    en_only_btn = widget.findChild(QPushButton, "CandidatesEnOnlyButton")
    assert table and cb_en and cb_fr and en_only_btn
    assert cb_en.isChecked() is True
    assert cb_fr.isChecked() is False
    # Only English candidate is shown by default
    assert table.proxy.rowCount() == 1

    # Checking FR shows both EN and FR candidates
    cb_fr.setChecked(True)
    assert table.proxy.rowCount() == 2

    # Clicking "EN uniquement" resets to EN only
    en_only_btn.click()
    assert cb_fr.isChecked() is False
    assert table.proxy.rowCount() == 1

    # Purge removes non-EN and canonical duplicates permanently from workspace
    rem_s, rem_c = purge_disallowed_languages_and_duplicates(ws, uid, ("en",))
    assert rem_c == 3
    assert [c["id"] for c in ws.candidates_for(uid)] == ["c-en"]
    widget.deleteLater()


def test_generalist_domain_anti_topic_drift_and_no_blind_score_inheritance(
    tmp_path: Path,
) -> None:
    from warframe_lore.v1.scraper.collect.crawl_filter import (
        is_generalist_domain,
        matches_universe_topic,
    )
    from warframe_lore.v1.scraper.collect.language_purge import (
        purge_disallowed_languages_and_duplicates,
    )
    from warframe_lore.v1.scraper.UI.workspace import WorkshopWorkspace
    from warframe_lore.v1.scraper.use_cases.apply_result import apply_result
    from warframe_lore.v1.scraper.use_cases.child_scoring import (
        child_authority_score,
    )

    assert is_generalist_domain("https://fr.wikipedia.org/wiki/Warframe") is True
    assert is_generalist_domain("https://en.wikipedia.org/wiki/Warframe") is True
    assert is_generalist_domain("https://www.warframe.com/en") is False
    assert is_generalist_domain("https://warframe.fandom.com/wiki/Excalibur") is False

    ws = WorkshopWorkspace(path=tmp_path / "workspace.json")
    uni = ws.create("Warframe")
    uid = str(uni["id"])
    ws.add_manual_source(uid, "https://en.wikipedia.org/wiki/Warframe")
    ws.add_manual_source(uid, "https://www.warframe.com/en")

    off_topic_wiki_urls = [
        "https://en.wikipedia.org/wiki/2013_en_jeu_vid%C3%A9o",
        "https://en.wikipedia.org/wiki/Pikmin_3",
        "https://en.wikipedia.org/wiki/Pikachu",
        "https://en.wikipedia.org/wiki/Pissenlit",
        "https://en.wikipedia.org/wiki/Piraterie",
        "https://en.wikipedia.org/wiki/Pilote_informatique",
    ]
    for bad_url in off_topic_wiki_urls:
        assert matches_universe_topic(bad_url, "", ["warframe"]) is False
        score, _ = child_authority_score(
            ws, uid, "https://en.wikipedia.org/wiki/Warframe", bad_url
        )
        assert score <= 0.10

    # On-topic Wikipedia child page scores >= 0.70
    on_topic_score, _ = child_authority_score(
        ws,
        uid,
        "https://en.wikipedia.org/wiki/Warframe",
        "https://en.wikipedia.org/wiki/Warframe_Digital_Extremes",
    )
    assert on_topic_score >= 0.70

    # Simulate a run returning off-language + off-topic Wikipedia child URLs
    pending = [
        {"url": u, "parent": "https://en.wikipedia.org/wiki/Warframe"}
        for u in off_topic_wiki_urls
    ] + [
        {
            "url": "https://www.warframe.com/de/news/lotus",
            "parent": "https://www.warframe.com/en",
        },
        {
            "url": "https://www.warframe.com/ja/news/lotus",
            "parent": "https://www.warframe.com/en",
        },
        {
            "url": "https://fr.wikipedia.org/wiki/Warframe",
            "parent": "https://en.wikipedia.org/wiki/Warframe",
        },
        {
            "url": "https://www.warframe.com/en/news/the-old-peace",
            "parent": "https://www.warframe.com/en",
        },
    ]
    apply_result(
        ws,
        {
            "ok": True,
            "runs": [
                {
                    "universeId": uid,
                    "docs": [],
                    "pending_children": pending,
                    "run": {"id": "run-drift", "universeIds": [uid], "status": "done"},
                }
            ],
        },
    )
    cands = ws.candidates_for(uid)
    assert [c["location"] for c in cands] == [
        "https://www.warframe.com/en/news/the-old-peace"
    ]
    # Newly discovered child pages must remain "proposed" (never auto-activated)
    assert cands[0]["status"] == "proposed"

    # Inject bloated off-topic & off-language sources and verify one-click purge
    for idx, bad_url in enumerate(off_topic_wiki_urls):
        ws.data["sources"].append(
            {
                "id": f"bad-src-{idx}",
                "universeId": uid,
                "kind": "website",
                "location": bad_url,
                "status": "approved",
                "selected": True,
                "score": 0.78,
                "discoveredBy": "manifest_review",
            }
        )
    rem_s, rem_c = purge_disallowed_languages_and_duplicates(ws, uid, ("en",))
    assert rem_s == len(off_topic_wiki_urls)
    assert rem_c == 0
    remaining_locs = {s["location"] for s in ws.sources_for(uid)}
    assert remaining_locs == {
        "https://en.wikipedia.org/wiki/Warframe",
        "https://www.warframe.com/en",
    }


def test_http_no_retry_on_403_fast_fail_429_and_github_utility_filters() -> None:
    import requests

    from warframe_lore.v1.scraper.adapters.outbound.http.request_flow import (
        request_with_retries,
    )
    from warframe_lore.v1.scraper.collect.crawl_filter import (
        keep_crawl_url,
        matches_universe_topic,
    )
    from warframe_lore.v1.scraper.collect.language import (
        detect_url_locale,
        is_url_language_allowed,
    )
    from warframe_lore.v1.scraper.observability.progress import ProgressReporter

    # 1. Language switcher & French forum topic slugs detected properly
    assert (
        detect_url_locale(
            "https://support.warframe.com/hc/change_language/zh-tw?return_to=%2Fhc%2Fzh-tw"
        )
        == "zh"
    )
    assert (
        detect_url_locale("https://support.warframe.com/hc/change_language/de") == "de"
    )
    assert (
        detect_url_locale(
            "https://forums.warframe.com/index.php?/forum/140-fran%C3%A7ais"
        )
        == "fr"
    )
    assert (
        is_url_language_allowed(
            "https://support.warframe.com/hc/change_language/ru", ("en",)
        )
        is False
    )

    # 2. GitHub UI chrome, dotfiles & e-commerce merch paths rejected
    for gh_chrome in (
        "https://github.com/WFCD/warframe-items/pulls",
        "https://github.com/WFCD/warframe-items/issues",
        "https://github.com/WFCD/warframe-items/actions",
        "https://github.com/WFCD/warframe-items/security",
        "https://github.com/WFCD/warframe-items/blob/master/.gitignore",
        "https://github.com/contact/report-content?content_url=https://github.com/WFCD/warframe-items",
    ):
        assert matches_universe_topic(gh_chrome, "", ["warframe"]) is False

    for utility_url in (
        "https://store.warframe.com/products/lotus-hoodie",
        "https://store.warframe.com/collections/tees",
        "https://www.warframe.com/login/steam",
        "https://support.warframe.com/hc/change_language/en-us",
        "https://forums.warframe.com/applications/core/interface/file/attachment.php?id=1",
    ):
        assert keep_crawl_url(utility_url, "", allowed_languages=("en",)) is False

    # 3. Permanent 403 fails on attempt 1 without retry; 429 retry-after=60 fails fast
    calls = {"403": 0, "429": 0}

    class _FakeResp:
        def __init__(self, status_code: int, headers: dict[str, str]) -> None:
            self.status_code = status_code
            self.headers = headers
            self.url = "https://forums.warframe.com/topic/1"
            self.content = b""
            self.encoding = "utf-8"

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise requests.HTTPError(f"{self.status_code} Client Error")

    class _Session403:
        def get(self, *_a: Any, **_kw: Any) -> _FakeResp:
            calls["403"] += 1
            return _FakeResp(403, {})

    class _Session429:
        def get(self, *_a: Any, **_kw: Any) -> _FakeResp:
            calls["429"] += 1
            return _FakeResp(429, {"Retry-After": "60"})

    with pytest.raises(requests.HTTPError):
        request_with_retries(
            session=_Session403(),
            url="https://forums.warframe.com/topic/1",
            headers={},
            params=None,
            allow_redirects=True,
            timeout=5.0,
            verify="",
            max_retries=3,
            backoff=1.5,
            reporter=ProgressReporter(),
            control=None,
            throttle=lambda: None,
        )
    assert calls["403"] == 1

    with pytest.raises(RuntimeError, match="retry-after=60"):
        request_with_retries(
            session=_Session429(),
            url="https://store.warframe.com/products/1",
            headers={},
            params=None,
            allow_redirects=True,
            timeout=5.0,
            verify="",
            max_retries=3,
            backoff=1.5,
            reporter=ProgressReporter(),
            control=None,
            throttle=lambda: None,
        )
    assert calls["429"] == 1


def test_semantic_noise_filter_and_graph_top_n_lod_ego_mode() -> None:
    from PySide6.QtWidgets import QApplication, QSpinBox

    from warframe_lore.v1.scraper.graph.html_template import HTML_TEMPLATE
    from warframe_lore.v1.scraper.semantic.rules import extract_chunk_rules
    from warframe_lore.v1.scraper.UI.graph.scene import filter_graph
    from warframe_lore.v1.scraper.UI.graph.view import GraphCanvas

    noisy_chunk = (
        "Albrecht Entrati belongs to the Orokin Empire on Planet Deimos. "
        "Your License and Upon Success or When Supporting will trigger Scrollbox. "
        "Removed the Helminth and Fixed Clients with Damage Survival Crowd Control. "
        "It's fine and I'm sure You're ready."
    )
    ents, _rels, _mens = extract_chunk_rules(
        noisy_chunk,
        doc_id="d-noise",
        chunk_id="d-noise::0",
        url="https://wiki.warframe.com/w/Albrecht_Entrati",
        doc_title="Albrecht Entrati",
    )
    names = {e.name for e in ents}
    assert "Albrecht Entrati" in names
    assert "Orokin Empire" in names
    for forbidden in (
        "Your License",
        "Upon Success",
        "When Supporting",
        "Removed the Helminth",
        "Scrollbox",
        "Fixed Clients",
        "Damage Survival Crowd Control",
        "Damage Survival",
        "It's",
        "I'm",
        "You're",
    ):
        assert forbidden not in names

    # Build a synthetic 120-node semantic graph and verify Top-N, min_degree,
    # Concepts unchecked by default, and Ego-Graph neighborhood dimming.
    _ = QApplication.instance() or QApplication([])
    nodes = [
        {
            "id": f"p-{i}",
            "kind": "Person",
            "label": f"Hero {i}",
            "attrs": {"mentions": 10},
        }
        for i in range(50)
    ] + [
        {
            "id": f"c-{i}",
            "kind": "Concept",
            "label": f"Idea {i}",
            "attrs": {"mentions": 2},
        }
        for i in range(70)
    ]
    edges = [
        {"source": "p-0", "target": f"p-{i}", "type": "ALLIED_WITH"}
        for i in range(1, 15)
    ] + [
        {"source": "p-1", "target": f"p-{i}", "type": "RELATED_TO"}
        for i in range(2, 6)
    ]
    kg = {"nodes": nodes, "edges": edges, "meta": {"mode": "knowledge"}}

    sub = filter_graph(kg, {"Person"}, max_nodes=10, min_degree=3)
    assert len(sub["nodes"]) <= 10
    assert sub["nodes"][0]["id"] == "p-0"
    assert sub["nodes"][0]["is_hub"] is True

    canvas = GraphCanvas(kg, knowledge_graph=kg)
    assert canvas.sidebar.checks["Concept"].isChecked() is False
    assert canvas.sidebar.checks["Person"].isChecked() is True
    max_spin = canvas.findChild(QSpinBox, "GraphMaxNodesSpin")
    deg_spin = canvas.findChild(QSpinBox, "GraphMinDegreeSpin")
    assert max_spin is not None and max_spin.value() == 200
    assert deg_spin is not None and deg_spin.value() == 3

    # Trigger Ego-Graph on p-1 (connected to p-0, p-2..p-5; not connected to p-10)
    deg_spin.setValue(0)
    by_id = {str(it.node["id"]): it for it in canvas._node_items}
    canvas.show_node(by_id["p-1"].node)
    assert by_id["p-1"].opacity() == 1.0
    assert by_id["p-0"].opacity() == 1.0
    assert by_id["p-10"].opacity() < 0.2
    canvas.clear_focus()
    assert by_id["p-10"].opacity() == 1.0
    canvas.close()

    assert 'id="max-nodes"' in HTML_TEMPLATE
    assert 'id="min-deg"' in HTML_TEMPLATE
    assert "Concept: !isSemantic" in HTML_TEMPLATE
    assert "shouldDrawLabel" in HTML_TEMPLATE
    assert "stopPhysics()" in HTML_TEMPLATE
