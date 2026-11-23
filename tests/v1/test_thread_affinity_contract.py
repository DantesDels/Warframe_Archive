"""Worker callbacks must reach Qt widgets on the main thread only."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from typing import Any

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import (  # noqa: E402
    QEventLoop,
    QObject,
    Qt,
    QThread,
    QTimer,
    Signal,
)
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from warframe_lore.v1.scraper.UI.runtime.discovery_runner import (  # noqa: E402
    start_discovery,
)
from warframe_lore.v1.scraper.UI.runtime.main_thread_bridge import (  # noqa: E402
    MainThreadBridge,
)


class _Emitter(QObject):
    done = Signal(object)
    event = Signal(str, object)


def _qt_app() -> QApplication:
    app = QApplication.instance()
    return app if isinstance(app, QApplication) else QApplication([])


def _run_briefly(stop: QThread) -> None:
    loop = QEventLoop()
    QTimer.singleShot(600, loop.quit)
    loop.exec()
    stop.quit()
    stop.wait(1000)


class ThreadAffinityContract(unittest.TestCase):
    def test_bridge_runs_callbacks_on_main_thread(self) -> None:
        _qt_app()
        main = QThread.currentThread()
        emitter = _Emitter()
        thread = QThread()
        emitter.moveToThread(thread)
        seen: list[QThread] = []

        def record(*_args: Any) -> None:
            seen.append(QThread.currentThread())

        bridge = MainThreadBridge(record)
        emitter.done.connect(bridge.on_value, Qt.ConnectionType.QueuedConnection)
        emitter.event.connect(bridge.on_event, Qt.ConnectionType.QueuedConnection)
        thread.start()
        emitter.done.emit("value")
        emitter.event.emit("type", {})
        _run_briefly(thread)
        self.assertEqual(seen, [main, main])

    def test_discovery_finishes_on_main_thread(self) -> None:
        from warframe_lore.v1.scraper.settings.models import Settings
        from warframe_lore.v1.scraper.UI.app import AtelierApp
        from warframe_lore.v1.scraper.UI.runtime import discovery_runner

        _qt_app()
        offline = Settings(
            discovery_sitemaps=False,
            discovery_feeds=False,
            discovery_wiki=False,
            graph_enabled=False,
        )
        with tempfile.TemporaryDirectory() as tmp:
            window = AtelierApp(data_path=Path(tmp) / "workspace.json")
            original = discovery_runner._finish
            seen: list[QThread] = []

            def record(app: object, thread: QThread, worker: QObject,
                       result: object, on_done: object) -> None:
                seen.append(QThread.currentThread())
                original(app, thread, worker, result, on_done)

            discovery_runner._finish = record  # type: ignore[assignment]
            try:
                start_discovery(
                    window, {"id": "u1", "name": "Test"},  # type: ignore[arg-type]
                    settings=offline,
                )
                loop = QEventLoop()
                QTimer.singleShot(1200, loop.quit)
                loop.exec()
            finally:
                discovery_runner._finish = original  # type: ignore[assignment]
                QMessageBox.information = staticmethod(  # type: ignore[assignment]
                    lambda *args, **kwargs: None
                )
                window.close()
            self.assertEqual(seen, [QThread.currentThread()])
            self.assertIsNone(getattr(window, "_discovery_bridge", None))


class DiscoveryTeardownContract(unittest.TestCase):
    def test_finish_waits_for_thread_and_keeps_newer_refs(self) -> None:
        from warframe_lore.v1.scraper.UI.runtime import discovery_runner

        class FakeThread:
            def __init__(self) -> None:
                self.quit_calls = 0
                self.wait_calls: list[int] = []

            def quit(self) -> None:
                self.quit_calls += 1

            def wait(self, ms: int) -> None:
                self.wait_calls.append(ms)

        class FakeWorker:
            def __init__(self) -> None:
                self.deleted = False

            def deleteLater(self) -> None:
                self.deleted = True

        class FakeExecution:
            def add_log(self, *_args: Any) -> None:
                pass

            def set_state(self, *_args: Any) -> None:
                pass

        class FakeApp:
            def __init__(self) -> None:
                self.execution = FakeExecution()
                self._discovery_thread: Any = None
                self._discovery_worker: Any = None
                self._discovery_launcher: Any = None
                self._discovery_bridge: Any = None

            def refresh(self) -> None:
                pass

        app = FakeApp()
        thread = FakeThread()
        worker = FakeWorker()
        app._discovery_thread = thread
        app._discovery_worker = worker
        result = {"ok": True, "count": 0}
        discovery_runner._finish(app, thread, worker, result, None)
        self.assertEqual(thread.quit_calls, 1)
        self.assertEqual(thread.wait_calls, [2000])
        self.assertFalse(worker.deleted)
        self.assertIsNone(app._discovery_thread)

        newer = FakeThread()
        app._discovery_thread = newer
        discovery_runner._finish(app, thread, worker, result, None)
        self.assertIs(app._discovery_thread, newer)


class PreviewAffinityContract(unittest.TestCase):
    def test_preview_runs_off_main_thread(self) -> None:
        import warframe_lore.v1.scraper.UI.views.candidates.preview_worker as preview

        _qt_app()
        original = preview.preview_child_candidates
        original_message = QMessageBox.information
        seen: list[QThread] = []

        def fake_preview(*_args: Any, **_kwargs: Any) -> list[Any]:
            seen.append(QThread.currentThread())
            return []

        QMessageBox.information = staticmethod(  # type: ignore[assignment]
            lambda *_args, **_kwargs: None
        )
        preview.preview_child_candidates = fake_preview  # type: ignore[assignment]
        owner = QObject()
        try:
            preview.start_preview(
                owner, object(), {"id": "u1"}, "https://example.invalid", lambda: None
            )
            loop = QEventLoop()
            QTimer.singleShot(700, loop.quit)
            loop.exec()
        finally:
            preview.preview_child_candidates = original  # type: ignore[assignment]
            QMessageBox.information = original_message
        self.assertEqual(len(seen), 1)
        self.assertIsNot(seen[0], QThread.currentThread())


class OperationGuardContract(unittest.TestCase):
    def test_discovery_refused_while_execution_runs(self) -> None:
        class FakeThread:
            def isRunning(self) -> bool:
                return True

        class FakeExecution:
            def __init__(self) -> None:
                self.state = ""

            def set_state(self, state: str, _message: str | None = None) -> None:
                self.state = state

        class FakeApp:
            def __init__(self) -> None:
                self.execution = FakeExecution()
                self._thread: Any = FakeThread()
                self._discovery_thread: Any = None

        app = FakeApp()
        start_discovery(app, {"id": "u1"})  # type: ignore[arg-type]
        self.assertEqual(app.execution.state, "busy")
        self.assertIsNone(app._discovery_thread)

    def test_execution_refused_while_discovery_runs(self) -> None:
        from warframe_lore.v1.scraper.UI.runner_ui import start_execution

        class FakeThread:
            def isRunning(self) -> bool:
                return True

        class FakeExecution:
            def __init__(self) -> None:
                self.state = ""
                self.logs: list[str] = []

            def set_state(self, state: str, _message: str | None = None) -> None:
                self.state = state

            def add_log(self, message: str) -> None:
                self.logs.append(message)

        class FakeApp:
            def __init__(self) -> None:
                self.execution = FakeExecution()
                self._thread: Any = None
                self._discovery_thread: Any = FakeThread()

        app = FakeApp()
        start_execution(app, object())
        self.assertEqual(app.execution.state, "busy")
        self.assertIsNone(app._thread)


if __name__ == "__main__":
    unittest.main()
