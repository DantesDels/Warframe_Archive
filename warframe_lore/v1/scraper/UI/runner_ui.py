"""Background execution orchestration for the PySide6 UI."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtCore import Qt, QThread

from ..use_cases.apply_result import apply_result
from .runtime.execution_events import format_event
from .runtime.main_thread_bridge import MainThreadBridge
from .runtime.snapshot import Snapshot
from .runtime.snapshot import snapshot as _snapshot
from .runtime.work_launcher import WorkLauncher
from .worker import ExecutionWorker

_Snapshot = Snapshot


def start_execution(app: Any, plan: Any) -> None:
    if getattr(app, "_thread", None) and app._thread.isRunning():
        app.execution.set_state("busy")
        app.execution.add_log("Une exécution est déjà en cours.")
        return
    discovery = getattr(app, "_discovery_thread", None)
    if discovery is not None and discovery.isRunning():
        app.execution.set_state("busy")
        app.execution.add_log("Une découverte est déjà en cours.")
        return
    cleanup_execution(app)
    app.execution.reset()
    app.execution.set_state("running", "Lancement de l'exécution...")
    snapshot = _snapshot(app.workspace)
    thread = QThread(app)
    worker = ExecutionWorker(plan, snapshot, app.data_path.parent / "exports")
    launcher = WorkLauncher()
    worker.moveToThread(thread)
    launcher.requested.connect(worker.run, Qt.ConnectionType.QueuedConnection)
    thread.started.connect(launcher.launch)
    thread.finished.connect(launcher.deleteLater)
    worker.progress.connect(app.execution.set_progress)
    worker.log.connect(app.execution.add_log)
    event_bridge = MainThreadBridge(
        lambda event_type, payload: _log_event(app, event_type, payload)
    )
    worker.events_log.connect(
        event_bridge.on_event, Qt.ConnectionType.QueuedConnection
    )
    _connect_controls(app, worker)
    app._worker = worker
    app._thread = thread
    app._launcher = launcher
    app._execution_event_bridge = event_bridge
    worker.finished.connect(
        app._on_execution_finished, Qt.ConnectionType.QueuedConnection
    )
    thread.start()


def _log_event(app: Any, event_type: str, payload: Any) -> None:
    message = format_event(event_type, payload)
    if message:
        app.execution.add_log(message)


def _connect_controls(app: Any, worker: ExecutionWorker) -> None:
    connections = [
        (app.execution.pause_btn, worker.control.pause),
        (app.execution.resume_btn, worker.control.resume),
        (app.execution.cancel_btn, worker.control.cancel),
        (app.execution.pause_btn, lambda: _set_paused(app, True)),
        (app.execution.resume_btn, lambda: _set_paused(app, False)),
        (app.execution.cancel_btn, lambda: app.execution.cancel_btn.setEnabled(False)),
    ]
    for button, slot in connections:
        button.clicked.connect(slot)
    app._control_connections = connections


def _disconnect_controls(app: Any) -> None:
    for button, slot in getattr(app, "_control_connections", []):
        try:
            button.clicked.disconnect(slot)
        except (RuntimeError, TypeError):
            pass
    app._control_connections = []


def _set_paused(app: Any, paused: bool) -> None:
    app.execution.set_state("paused" if paused else "running")


def cleanup_execution(app: Any, *, stop: bool = True) -> None:
    """Disconnect controls, stop the worker thread and release Qt objects."""
    thread = getattr(app, "_thread", None)
    worker = getattr(app, "_worker", None)
    _disconnect_controls(app)
    if stop and worker is not None:
        worker.control.cancel()
    if thread is not None:
        try:
            if thread.isRunning():
                thread.quit()
                thread.wait(2000)
            thread.deleteLater()
        except RuntimeError:
            pass
    app._worker = None
    app._thread = None
    app._launcher = None
    app._execution_event_bridge = None


def handle_finished(app: Any, result: object) -> None:
    thread = getattr(app, "_thread", None)
    if thread:
        thread.quit()
    result_dict = cast(dict[str, Any], result) if isinstance(result, dict) else None
    if result_dict is not None and (
        result_dict.get("ok") or result_dict.get("cancelled")
    ):
        apply_result(app.workspace, result_dict)
    app.refresh()
    if result_dict and result_dict.get("cancelled"):
        app.execution.set_state("cancelled")
    elif result_dict and result_dict.get("ok"):
        app.execution.set_state("done")
    else:
        app.execution.set_state("error")
    cleanup_execution(app, stop=False)
