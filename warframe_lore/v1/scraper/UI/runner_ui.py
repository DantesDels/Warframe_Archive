"""Background execution orchestration for the PySide6 UI."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtCore import Qt, QThread

from ..use_cases.apply_result import apply_result
from .worker import ExecutionWorker


def start_execution(app: Any, plan: Any) -> None:
    if getattr(app, "_thread", None) and app._thread.isRunning():
        app.execution.set_state("busy")
        app.execution.add_log("Une exécution est déjà en cours.")
        return
    cleanup_execution(app)
    app.execution.reset()
    app.execution.add_log("Lancement de l'exécution...")
    snapshot = _snapshot(app.workspace)
    thread = QThread(app)
    worker = ExecutionWorker(plan, snapshot, app.data_path.parent / "exports")
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.progress.connect(app.execution.set_progress)
    worker.log.connect(app.execution.add_log)
    _connect_controls(app, worker)
    app._worker = worker
    app._thread = thread
    worker.finished.connect(
        app._on_execution_finished, Qt.ConnectionType.QueuedConnection
    )
    thread.start()


def _connect_controls(app: Any, worker: ExecutionWorker) -> None:
    connections = [
        (app.execution.pause_btn, worker.pause),
        (app.execution.resume_btn, worker.resume),
        (app.execution.cancel_btn, worker.cancel),
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


class _Snapshot:
    def __init__(self, data: dict[str, Any]) -> None:
        self.universes = {u["id"]: dict(u) for u in data.get("universes", [])}
        self.sources_by_uid = _group(data.get("sources", []), "universeId")
        self.candidates_by_uid = _group(data.get("candidates", []), "universeId")
        caps = data.get("capabilities", {})
        self.capabilities_by_uid = {k: dict(v) for k, v in caps.items()}

    def get(self, uid: str) -> dict[str, Any] | None:
        return self.universes.get(uid)


def _snapshot(workspace: Any) -> _Snapshot:
    return _Snapshot(workspace.data)


def _group(items: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        uid = str(item.get(key, ""))
        if uid:
            out.setdefault(uid, []).append(dict(item))
    return out


def cleanup_execution(app: Any, *, stop: bool = True) -> None:
    """Disconnect controls, stop the worker thread and release Qt objects."""
    thread = getattr(app, "_thread", None)
    worker = getattr(app, "_worker", None)
    _disconnect_controls(app)
    if stop and worker is not None:
        worker.cancel()
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
