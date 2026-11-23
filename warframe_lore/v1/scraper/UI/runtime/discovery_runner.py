"""Run source discovery off the Qt main thread."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, Qt, QThread, Signal

from ...collect.http import HttpClient
from ...observability.network import HTTP_TIMEOUT
from ...use_cases.discover_universe import discover_universe
from .main_thread_bridge import MainThreadBridge
from .work_launcher import WorkLauncher


class DiscoveryWorker(QObject):
    """Perform one universe discovery inside a QThread."""

    finished = Signal(object)

    def __init__(
        self, app: Any, universe: dict[str, Any], settings: Any | None = None
    ) -> None:
        super().__init__()
        self.workspace = app.workspace
        self.universe = universe
        self.settings = settings if settings is not None else app.settings_store.load()

    def run(self) -> None:
        try:
            client = HttpClient(timeout=HTTP_TIMEOUT, max_retries=1, min_sleep=0.0)
            count = discover_universe(
                self.workspace, self.universe, self.settings, client=client
            )
            self.finished.emit({"ok": True, "count": len(count)})
        except Exception as exc:  # noqa: BLE001
            self.finished.emit({"ok": False, "error": str(exc)})


def start_discovery(
    app: Any,
    universe: dict[str, Any],
    on_done: Callable[[int], None] | None = None,
    settings: Any | None = None,
) -> None:
    """Launch discovery and invoke ``on_done`` on the main thread."""
    existing = getattr(app, "_discovery_thread", None)
    execution = getattr(app, "_thread", None)
    if (existing is not None and existing.isRunning()) or (
        execution is not None and execution.isRunning()
    ):
        app.execution.set_state("busy", "Opération déjà en cours.")
        return
    app.execution.set_state("running", "Découverte en cours...")
    thread = QThread(app)
    worker = DiscoveryWorker(app, universe, settings)
    launcher = WorkLauncher()
    worker.moveToThread(thread)
    launcher.requested.connect(worker.run, Qt.ConnectionType.QueuedConnection)
    thread.started.connect(launcher.launch)
    thread.finished.connect(launcher.deleteLater)
    bridge = MainThreadBridge(
        lambda result: _finish(app, thread, worker, result, on_done)
    )
    worker.finished.connect(bridge.on_value, Qt.ConnectionType.QueuedConnection)
    app._discovery_thread = thread
    app._discovery_worker = worker
    app._discovery_launcher = launcher
    app._discovery_bridge = bridge
    thread.start()


_DISCOVERY_ATTRS = (
    "_discovery_thread",
    "_discovery_worker",
    "_discovery_launcher",
    "_discovery_bridge",
)


def _clear_refs(app: Any, thread: QThread) -> None:
    """Clear discovery refs only when they still belong to this thread."""
    if getattr(app, "_discovery_thread", None) is not thread:
        return
    for name in _DISCOVERY_ATTRS:
        setattr(app, name, None)


def cleanup_discovery(app: Any) -> None:
    """Stop a discovery thread still running when the window closes."""
    thread = getattr(app, "_discovery_thread", None)
    if thread is not None and thread.isRunning():
        thread.quit()
        thread.wait(2000)
    for name in _DISCOVERY_ATTRS:
        setattr(app, name, None)


def _finish(app: Any, thread: QThread, worker: QObject, result: object,
            on_done: Callable[[int], None] | None) -> None:
    payload = result if isinstance(result, dict) else {}
    if payload.get("ok"):
        count = int(payload.get("count", 0))
        app.execution.add_log(f"{count} nouveau(x) candidat(s) découvert(s).")
    else:
        count = 0
        app.execution.add_log(f"Découverte impossible : {payload.get('error', '')}")
    app.execution.set_state("idle", "Découverte terminée.")
    app.refresh()
    thread.quit()
    thread.wait(2000)
    _clear_refs(app, thread)
    if on_done is not None:
        on_done(count)
