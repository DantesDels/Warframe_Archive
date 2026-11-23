"""Non-blocking child-page preview for the candidates table."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtWidgets import QMessageBox

from ....collect.http import HttpClient
from ....settings import SettingsStore
from ....use_cases.review_children import preview_child_candidates
from ...runtime.main_thread_bridge import MainThreadBridge
from ...runtime.work_launcher import WorkLauncher

_PREVIEW_ATTRS = (
    "_preview_thread",
    "_preview_worker",
    "_preview_launcher",
    "_preview_bridge",
)


class PreviewWorker(QObject):
    """Fetch child pages inside a worker thread."""

    finished = Signal(object)

    def __init__(self, workspace: Any, universe: dict[str, Any], location: str) -> None:
        super().__init__()
        self.workspace = workspace
        self.universe = universe
        self.location = location

    def run(self) -> None:
        try:
            ws_path = getattr(self.workspace, "path", None)
            use_pw = False
            if ws_path is not None:
                store = SettingsStore(ws_path.parent / "settings.json")
                use_pw = store.load().use_playwright
            children = preview_child_candidates(
                self.workspace,
                self.universe,
                self.location,
                client=HttpClient(),
                use_playwright=use_pw,
            )
            self.finished.emit({"ok": True, "count": len(children)})
        except Exception as exc:  # noqa: BLE001
            self.finished.emit({"ok": False, "error": str(exc)})


def start_preview(
    owner: Any,
    workspace: Any,
    universe: dict[str, Any],
    location: str,
    on_change: Callable[[], None],
) -> None:
    """Launch a preview without blocking the UI thread."""
    existing = getattr(owner, "_preview_thread", None)
    if existing is not None and existing.isRunning():
        return
    thread = QThread()
    worker = PreviewWorker(workspace, universe, location)
    launcher = WorkLauncher()
    worker.moveToThread(thread)
    launcher.requested.connect(worker.run, Qt.ConnectionType.QueuedConnection)
    thread.started.connect(launcher.launch)
    thread.finished.connect(launcher.deleteLater)
    bridge = MainThreadBridge(lambda result: _finish(owner, result, on_change))
    worker.finished.connect(bridge.on_value, Qt.ConnectionType.QueuedConnection)
    owner._preview_thread = thread
    owner._preview_worker = worker
    owner._preview_launcher = launcher
    owner._preview_bridge = bridge
    thread.start()


def _finish(
    owner: Any, result: object, on_change: Callable[[], None]
) -> None:
    payload = result if isinstance(result, dict) else {}
    if payload.get("ok"):
        count = int(payload.get("count", 0))
        QMessageBox.information(
            None,
            "Prévisualisation",
            f"{count} page(s) enfant(s) ajoutée(s) comme candidats à valider.",
        )
        on_change()
    else:
        QMessageBox.warning(
            None,
            "Prévisualisation",
            f"Impossible de prévisualiser : {payload.get('error', '')}",
        )
    thread = getattr(owner, "_preview_thread", None)
    if thread is not None:
        thread.quit()
        thread.wait(2000)
    for name in _PREVIEW_ATTRS:
        setattr(owner, name, None)
