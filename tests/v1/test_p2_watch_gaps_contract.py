"""Phase P2 contracts: conditional watchers, delta scheduler, KnowledgeGap & UI."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
import urllib.request
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QCheckBox,
    QPushButton,
    QSpinBox,
)

from warframe_lore.v1.scraper.discovery.models import Candidate  # noqa: E402
from warframe_lore.v1.scraper.gaps import (  # noqa: E402
    KnowledgeGap,
    build_discovery_queries,
    discover_for_gap,
    gaps_for,
    ingest_jsonl,
    record_gap,
    start_gaps_server,
)
from warframe_lore.v1.scraper.settings import Settings  # noqa: E402
from warframe_lore.v1.scraper.UI import WorkshopWorkspace, empty_data  # noqa: E402
from warframe_lore.v1.scraper.UI.views.gaps import gaps_view  # noqa: E402
from warframe_lore.v1.scraper.UI.views.simple_table import SimpleTable  # noqa: E402
from warframe_lore.v1.scraper.UI.views.watch import watch_view  # noqa: E402
from warframe_lore.v1.scraper.watch import (  # noqa: E402
    LocalWatchScheduler,
    check_universe_watch,
    infer_watcher_kind,
    run_targeted_delta,
    watch_url_for,
)


def _qt() -> QApplication:
    app = QApplication.instance()
    return app if isinstance(app, QApplication) else QApplication([])


class _FakeHttpClient:
    """Sequence-driven conditional HTTP client recording request headers."""

    def __init__(self, responses: list[SimpleNamespace]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, dict[str, str]]] = []

    def get(
        self, url: str, *, headers: dict[str, str], timeout: tuple[float, float]
    ) -> SimpleNamespace:
        self.calls.append((url, dict(headers)))
        return self._responses.pop(0)


class WatchersContractTests(unittest.TestCase):
    def test_watcher_classification_and_github_release_endpoint(self) -> None:
        gh = {"location": "https://github.com/org/codex", "kind": "website"}
        self.assertEqual(infer_watcher_kind(gh), "github_release")
        self.assertEqual(
            watch_url_for(gh, "github_release"),
            "https://api.github.com/repos/org/codex/releases?per_page=5",
        )
        self.assertEqual(
            infer_watcher_kind({"location": "https://x.org/rss.xml", "kind": "feed"}),
            "rss",
        )
        self.assertEqual(
            infer_watcher_kind(
                {"location": "https://x.org/sitemap.xml", "kind": "website"}
            ),
            "sitemap",
        )

    def test_conditional_etag_304_and_change_detection_cycle(self) -> None:
        ws = WorkshopWorkspace(data=empty_data())
        ws.create("Atlas")
        ws.add_manual_source("atlas", "https://example.org/feed.xml", kind="feed")
        rss_v1 = b"<rss><channel><item><title>Patch 1.0</title></item></channel></rss>"
        rss_v2 = b"<rss><channel><item><title>Patch 1.1</title></item></channel></rss>"
        client = _FakeHttpClient([
            SimpleNamespace(status_code=200, headers={"ETag": '"v1"'}, content=rss_v1),
            SimpleNamespace(status_code=304, headers={"ETag": '"v1"'}, content=b""),
            SimpleNamespace(status_code=200, headers={"ETag": '"v2"'}, content=rss_v2),
        ])
        r1 = check_universe_watch(ws, "atlas", client=client)
        self.assertEqual(r1.checked, 1)
        self.assertEqual(r1.changed_source_ids, [])  # baseline recorded

        r2 = check_universe_watch(ws, "atlas", client=client)
        self.assertEqual(client.calls[1][1].get("If-None-Match"), '"v1"')
        self.assertTrue(r2.results[0].not_modified)
        self.assertEqual(r2.changed_source_ids, [])

        r3 = check_universe_watch(ws, "atlas", client=client)
        self.assertEqual(len(r3.changed_source_ids), 1)
        self.assertIn("Patch 1.1", r3.results[0].detected_items)

    def test_scheduler_and_targeted_delta_only_collect_changed_sources(self) -> None:
        ws = WorkshopWorkspace(data=empty_data())
        ws.create("Atlas")
        s1 = ws.add_manual_source(
            "atlas", "https://example.org/changelog", kind="website"
        )
        ws.add_manual_source("atlas", "https://example.org/static", kind="website")
        s1["watch_state"] = {"fingerprint": "old-fp", "etag": '"old"'}
        caps = ws.capabilities_for("atlas")
        caps["watch"]["enabled"] = True
        caps["watch"]["poll_minutes"] = 30
        ws.set_capabilities("atlas", caps)

        client = _FakeHttpClient([
            SimpleNamespace(
                status_code=200, headers={"ETag": '"new"'}, content=b"Update 2"
            ),
            SimpleNamespace(status_code=200, headers={}, content=b"Static baseline"),
        ])
        triggered: list[tuple[str, list[str]]] = []
        sched = LocalWatchScheduler(
            ws,
            client=client,
            on_changes=lambda uid, rep: triggered.append((uid, rep.changed_source_ids)),
        )
        reports = sched.poll_due_once()
        self.assertEqual(len(reports), 1)
        self.assertEqual(triggered, [("atlas", [s1["id"]])])
        self.assertEqual(sched.poll_due_once(), [])  # interval not elapsed

        captured_sources: list[str] = []

        def _fake_collect(ctx, universe, _formats, limits):
            captured_sources.extend(
                str(s["id"]) for s in ctx.snapshot.sources_by_uid[universe["id"]]
            )
            self.assertTrue(limits["incremental"])
            return {
                "universeId": "atlas",
                "docs": [{
                    "id": "doc-delta", "universeId": "atlas", "sourceId": s1["id"],
                    "title": "Update 2", "url": "https://example.org/changelog",
                    "content": "Update 2", "checksum": "chk",
                }],
                "run": {
                    "id": "run-delta", "universeIds": ["atlas"], "status": "completed"
                },
                "pendingChildren": [],
            }

        summary = run_targeted_delta(
            ws, "atlas", [s1["id"]], settings=Settings(), collector=_fake_collect
        )
        self.assertEqual(captured_sources, [s1["id"]])
        self.assertEqual(summary["documents"], 1)


class KnowledgeGapContractTests(unittest.TestCase):
    def test_jsonl_ingestion_dedupe_priority_and_targeted_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = WorkshopWorkspace(path=Path(tmp) / "workspace.json")
            ws.create("Warframe")
            jsonl = Path(tmp) / "gaps.jsonl"
            jsonl.write_text(
                "\n".join([
                    json.dumps({
                        "universe_id": "warframe",
                        "question": "Qui est Albrecht Entrati ?",
                        "confidence": 0.2,
                    }),
                    json.dumps({
                        "universe_id": "Warframe",
                        "question": "  qui est albrecht entrati ? ",
                        "confidence": 0.1,
                    }),
                    json.dumps({
                        "universe_id": "warframe",
                        "question": "Quelles sont les reliques Lith ?",
                        "confidence": 0.65,
                    }),
                    "{invalid json",
                ]),
                encoding="utf-8",
            )
            ingested = ingest_jsonl(ws, jsonl)
            self.assertEqual(len(ingested), 3)
            ranked = gaps_for(ws, "warframe")
            self.assertEqual(len(ranked), 2)
            self.assertEqual(ranked[0]["hits"], 2)
            self.assertAlmostEqual(ranked[0]["confidence"], 0.1)
            queries = build_discovery_queries("Qui est Albrecht Entrati ?", "Warframe")
            self.assertTrue(any("Albrecht" in q and "Entrati" in q for q in queries))

            def _fake_discover(universe, **_kw):
                return [
                    Candidate(
                        id="cand-gap-1",
                        universe_id="warframe",
                        kind="wiki",
                        location="https://wiki.warframe.com/w/Albrecht_Entrati",
                        title="Albrecht Entrati",
                        score=0.92,
                        proof="wiki probe",
                    )
                ]

            added = discover_for_gap(
                ws,
                KnowledgeGap.from_dict(ranked[0]),
                Settings(),
                discover_fn=_fake_discover,
            )
            self.assertEqual(len(added), 1)
            self.assertIn("Lacune", added[0]["proof"])
            self.assertEqual(gaps_for(ws, "warframe")[1]["status"], "approved")

    def test_local_gaps_http_endpoint_ingests_and_lists_gaps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = WorkshopWorkspace(path=Path(tmp) / "workspace.json")
            ws.create("Dune")
            handle = start_gaps_server(ws, host="127.0.0.1", port=0)
            try:
                body = json.dumps({
                    "universe_id": "dune",
                    "question": "Comment fonctionne l'Épice sur Arrakis ?",
                    "confidence": 0.15,
                    "source": "discord-bot",
                }).encode("utf-8")
                req = urllib.request.Request(
                    handle.url,
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    self.assertEqual(resp.status, 201)
                    data = json.loads(resp.read().decode("utf-8"))
                    self.assertEqual(data["ingested"], 1)
                url_q = f"{handle.url}?universe_id=dune"
                with urllib.request.urlopen(url_q, timeout=5) as r:
                    listed = json.loads(r.read().decode("utf-8"))
                    self.assertEqual(listed["count"], 1)
                self.assertTrue((Path(tmp) / "gaps.jsonl").is_file())
            finally:
                handle.stop()

    def test_watch_and_gaps_ui_tabs(self) -> None:
        _qt()
        with tempfile.TemporaryDirectory() as tmp:
            ws = WorkshopWorkspace(path=Path(tmp) / "workspace.json")
            ws.create("Codex")
            src = ws.add_manual_source(
                "codex", "https://codex.example/rss.xml", kind="feed"
            )
            src["watch_state"] = {"last_changed": True, "last_reason": "Nouveau billet"}
            record_gap(ws, "codex", "Comment forger l'épée lunaire ?", confidence=0.1)

            wtab = watch_view(ws, ws.get("codex"), lambda: None)
            cb = wtab.findChild(QCheckBox, "WatchEnabledCheck")
            spin = wtab.findChild(QSpinBox, "WatchPollMinutes")
            delta_btn = wtab.findChild(QPushButton, "WatchRunDeltaButton")
            assert cb and spin and delta_btn
            self.assertTrue(delta_btn.isEnabled())
            cb.setChecked(True)
            spin.setValue(15)
            self.assertTrue(ws.capabilities_for("codex")["watch"]["enabled"])
            self.assertEqual(ws.capabilities_for("codex")["watch"]["poll_minutes"], 15)
            wtab.deleteLater()

            gtab = gaps_view(ws, ws.get("codex"), lambda: None)
            table = gtab.findChild(SimpleTable)
            sel_all = gtab.findChild(QPushButton, "GapsSelectAllButton")
            assert table and sel_all
            sel_all.click()
            self.assertEqual(len(table.selected_ids()), 1)
            resolve_btn = next(
                b for b in gtab.findChildren(QPushButton)
                if b.text() == "Marquer résolue"
            )
            resolve_btn.click()
            self.assertEqual(gaps_for(ws, "codex")[0]["status"], "resolved")
            ep_btn = gtab.findChild(QPushButton, "GapsEndpointButton")
            assert ep_btn is not None
            self.assertEqual(ep_btn.text(), "Démarrer /gaps")
            ep_btn.click()
            try:
                self.assertEqual(ep_btn.text(), "Arrêter /gaps")
                self.assertIsNotNone(getattr(ws, "_gaps_server", None))
            finally:
                ep_btn.click()
            self.assertIsNone(getattr(ws, "_gaps_server", None))
            self.assertEqual(ep_btn.text(), "Démarrer /gaps")
            gtab.deleteLater()

    def test_child_authority_spa_preview_and_discovery_progress_100(self) -> None:
        from unittest.mock import patch

        from warframe_lore.v1.scraper.collect.spa import SpaRenderResult, looks_like_spa
        from warframe_lore.v1.scraper.UI.execution_panel import ExecutionPanel
        from warframe_lore.v1.scraper.UI.runtime.discovery_runner import _finish
        from warframe_lore.v1.scraper.use_cases.child_scoring import (
            child_authority_score,
        )
        from warframe_lore.v1.scraper.use_cases.review_children import (
            preview_child_candidates,
        )

        ws = WorkshopWorkspace(data=empty_data())
        ws.create("Warframe")
        ws.add_manual_source(
            "warframe", "https://www.warframe.com/en/game", kind="website"
        )
        score, bd = child_authority_score(
            ws,
            "warframe",
            "https://www.warframe.com/en/game/warframes",
            "https://www.warframe.com/en/game/warframes/ash",
        )
        self.assertGreaterEqual(score, 0.85)
        self.assertEqual(bd["same_host"], 1.0)

        spa_html = (
            '<html><body><div id="app"></div>'
            '<script type="module"></script></body></html>'
        )
        self.assertTrue(looks_like_spa(spa_html, 2))
        fake_client = SimpleNamespace(
            get=lambda _u, **_kw: SimpleNamespace(
                url="https://www.warframe.com/en/game/warframes",
                headers={"content-type": "text/html"},
                encoding="utf-8",
                content=spa_html.encode("utf-8"),
            )
        )
        fake_render = SpaRenderResult(
            final_url="https://www.warframe.com/en/game/warframes",
            title="Warframes",
            html=spa_html,
            links=[
                "https://www.warframe.com/en/game/warframes/ash",
                "https://www.warframe.com/en/game/warframes/atlas-prime",
                "https://www.warframe.com/en/login",
            ],
        )
        with patch(
            "warframe_lore.v1.scraper.use_cases.review_children.render_spa_page",
            return_value=fake_render,
        ), patch(
            "warframe_lore.v1.scraper.use_cases.review_children.playwright_available",
            return_value=True,
        ):
            children = preview_child_candidates(
                ws,
                ws.get("warframe"),
                "https://www.warframe.com/game/warframes",
                client=fake_client,
            )
        urls = [c["location"] for c in children]
        self.assertEqual(
            urls,
            [
                "https://www.warframe.com/en/game/warframes/ash",
                "https://www.warframe.com/en/game/warframes/atlas-prime",
            ],
        )
        self.assertTrue(all(c["score"] >= 0.85 for c in children))

        _qt()
        panel = ExecutionPanel()
        panel.set_state("running", "Découverte en cours...")
        fake_thread = SimpleNamespace(quit=lambda: None, wait=lambda _ms: None)
        fake_app = SimpleNamespace(
            execution=panel,
            refresh=lambda: None,
            _discovery_thread=fake_thread,
        )
        _finish(
            fake_app, fake_thread, SimpleNamespace(), {"ok": True, "count": 4}, None
        )
        self.assertEqual(panel.state, "done")
        self.assertEqual(panel.progress.value(), 100)
        self.assertIn("Découverte terminée.", panel.step_label.text())
        panel.deleteLater()


if __name__ == "__main__":
    unittest.main()
