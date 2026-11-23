"""Background execution orchestration for the PySide6 UI."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtCore import Qt, QThread

from ..use_cases.apply_result import apply_result
from .worker import ExecutionWorker


def start_execution(app: Any, plan: Any) -> None:
    if getattr(app, "_thread", None) and app._thread.isRunning():
        return
    app.status_bar.showMessage("Statut : Ex?cution en cours")
    snapshot = _snapshot(app.workspace)
    thread = QThread(app)
    worker = ExecutionWorker(plan, snapshot, app.data_path.parent / "exports")
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.progress.connect(app.execution.set_progress)
    worker.log.connect(app.execution.add_log)
    app._worker = worker
    app._thread = thread
    worker.finished.connect(
        app._on_execution_finished, Qt.ConnectionType.QueuedConnection
    )
    thread.finished.connect(thread.deleteLater)
    app.execution.reset()
    thread.start()


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


def cleanup_execution(app: Any) -> None:
    thread = getattr(app, "_thread", None)
    worker = getattr(app, "_worker", None)
    if thread and thread.isRunning():
        thread.quit()
        thread.wait(1500)
    if worker:
        worker.deleteLater()
    app._worker = None
    app._thread = None


def handle_finished(app: Any, result: object) -> None:
    thread = getattr(app, "_thread", None)
    if thread:
        thread.quit()
    result_dict = cast(dict[str, Any], result) if isinstance(result, dict) else None
    if result_dict is not None and result_dict.get("ok"):
        apply_result(app.workspace, result_dict)
    app.refresh()
    app.status_bar.showMessage("Statut : Pr?t")
