"""Execution observability and cooperative control contracts."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QStatusBar  # noqa: E402

from warframe_lore.v1.scraper.adapters.outbound.connectors.html import (  # noqa: E402
    collect_html,
)
from warframe_lore.v1.scraper.collect.http import HttpClient  # noqa: E402
from warframe_lore.v1.scraper.observability import (  # noqa: E402
    HTTP_TIMEOUT,
    ProgressEvent,
    ProgressReporter,
)
from warframe_lore.v1.scraper.observability.progress import stop_requested  # noqa: E402
from warframe_lore.v1.scraper.ports.outbound.sources import (
    ConnectorContext,  # noqa: E402
)
from warframe_lore.v1.scraper.UI.execution_panel import ExecutionPanel  # noqa: E402
from warframe_lore.v1.scraper.UI.runner_ui import _connect_controls  # noqa: E402
from warframe_lore.v1.scraper.UI.runtime.execution_events import (  # noqa: E402
    format_event,
)
from warframe_lore.v1.scraper.UI.worker import ExecutionWorker  # noqa: E402
from warframe_lore.v1.scraper.use_cases.run_controls import RunControl  # noqa: E402


class _Response:
    def __init__(self, url: str, body: str, content_type: str = "text/html") -> None:
        self.url = url
        self.content = body.encode("utf-8")
        self.content_type = content_type
        self.encoding = "utf-8"
        self.from_cache = False


class _Client:
    def __init__(self, *, on_first: Any = None) -> None:
        self.on_first = on_first
        self.calls: list[str] = []

    def get(self, url: str, **_kwargs: Any) -> _Response:
        self.calls.append(url)
        if self.on_first is not None and len(self.calls) == 1:
            self.on_first()
        if url.endswith("/start"):
            body = (
                "<html><body><a href='/page2'>2</a>"
                "<a href='/page3'>3</a></body></html>"
            )
            return _Response(url, body)
        return _Response(url, f"<html><body>{url}</body></html>")


def _qt_app() -> QApplication:
    app = QApplication.instance()
    return app if isinstance(app, QApplication) else QApplication([])


class ProgressStreamingTests(unittest.TestCase):
    def test_reporter_emits_source_and_page_events(self) -> None:
        events: list[ProgressEvent] = []
        reporter = ProgressReporter(events.append)
        reporter.source(1, 2, "https://wiki.test")
        reporter.page(3, 25, "https://wiki.test/page")
        stages = [event.stage for event in events]
        self.assertEqual(stages, ["source", "page"])
        self.assertIn("Source 1/2 : https://wiki.test", events[0].message)
        self.assertIn("Page 3/25", events[1].message)
        self.assertGreater(events[1].percent, events[0].percent)

    def test_html_crawl_streams_one_event_per_page(self) -> None:
        events: list[ProgressEvent] = []
        reporter = ProgressReporter(events.append)
        reporter.source(1, 1, "https://wiki.test/start")
        limits: dict[str, Any] = {
            "reporter": reporter,
            "max_pages_per_source": 3,
            "max_depth": 1,
            "same_host_only": True,
        }
        pages = collect_html(
            "https://wiki.test/start",
            ConnectorContext(client=_Client(), limits=limits),
        )
        self.assertEqual(len(pages), 3)
        self.assertEqual(
            [event.stage for event in events].count("page"), 3
        )
        self.assertTrue(all("Page " in event.message for event in events[1:]))

    def test_cancel_stops_multipage_crawl_after_current_page(self) -> None:
        control = RunControl()
        client = _Client(on_first=control.cancel)
        limits: dict[str, Any] = {
            "control": control,
            "max_pages_per_source": 25,
            "max_depth": 3,
        }
        pages = collect_html(
            "https://wiki.test/start", ConnectorContext(client=client, limits=limits)
        )
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(len(pages), 1)
        self.assertTrue(stop_requested(limits))


class UiSynchronizationTests(unittest.TestCase):
    def test_events_update_status_progress_and_log_together(self) -> None:
        _qt_app()
        panel = ExecutionPanel()
        status_bar = QStatusBar()
        panel.set_status_bar(status_bar)
        panel.reset()
        events: list[ProgressEvent] = []

        def capture(event: ProgressEvent) -> None:
            events.append(event)
            panel.on_event(event)

        reporter = ProgressReporter(capture)
        reporter.source(1, 2, "wiki.test")
        reporter.page(4, 25, "https://wiki.test/page")
        reporter.info("Contenu inchangé, ignoré")
        self.assertIn("Source 1/2 — Page 4/25", panel.step_label.text())
        self.assertIn("Source 1/2 : wiki.test", panel.logs.toPlainText())
        self.assertIn("Page 4/25", panel.logs.toPlainText())
        self.assertGreater(panel.progress.value(), 0)
        self.assertEqual(status_bar.currentMessage(), "Statut : Exécution en cours")
        self.assertTrue(panel.cancel_btn.isEnabled())
        self.assertTrue(panel.ticker.active)
        self.assertIn(":", panel.step_label.text().split("•")[-1])
        panel.set_state("done")
        self.assertFalse(panel.ticker.active)

    def test_control_buttons_reach_control_synchronously(self) -> None:
        _qt_app()
        panel = ExecutionPanel()
        panel.set_state("running")
        control = SimpleNamespace(
            pause=lambda: calls.append("pause"),
            resume=lambda: calls.append("resume"),
            cancel=lambda: calls.append("cancel"),
        )
        calls: list[str] = []
        app = SimpleNamespace(execution=panel, _control_connections=[])
        _connect_controls(app, cast(Any, SimpleNamespace(control=control)))
        panel.pause_btn.click()
        panel.resume_btn.click()
        panel.cancel_btn.click()
        self.assertEqual(calls, ["pause", "resume", "cancel"])

    def test_worker_reporter_streams_sources_and_http_into_signals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            worker = ExecutionWorker(
                SimpleNamespace(settings=None, universe_ids=()),
                SimpleNamespace(),
                Path(tmp) / "exports",
            )
            logs: list[str] = []
            progress: list[tuple[int, str]] = []
            worker.log.connect(logs.append)
            worker.progress.connect(
                lambda percent, step: progress.append((percent, step))
            )
            worker.reporter.source(1, 2, "wiki.test")
            worker.reporter.http("https://wiki.test", 200)
            self.assertTrue(any("Source 1/2" in line for line in logs))
            self.assertTrue(any("Requête HTTP 200" in line for line in logs))
            self.assertEqual(len(progress), 2)

    def test_pipeline_events_have_french_log_lines(self) -> None:
        self.assertEqual(
            format_event("universe_started", {"sources": 3}),
            "Univers démarré : 3 source(s) active(s).",
        )
        self.assertEqual(
            format_event("children_pending_review", {"count": 2}),
            "2 page(s) enfant(s) en attente de revue.",
        )
        self.assertEqual(format_event("unknown", {}), "")

    def test_http_client_uses_explicit_connect_and_read_timeouts(self) -> None:
        self.assertEqual(HTTP_TIMEOUT, (5.0, 15.0))
        with tempfile.TemporaryDirectory() as tmp:
            client = HttpClient(timeout=HTTP_TIMEOUT)
            self.assertEqual(client.timeout, (5.0, 15.0))
            self.assertIsNotNone(Path(tmp))


if __name__ == "__main__":
    unittest.main()
