"""Background execution orchestration for the PySide6 UI."""

from __future__ import annotations

from PySide6.QtCore import Qt, QThread

from .worker import ExecutionWorker


def start_execution(app, plan) -> None:
    if getattr(app, "_thread", None) and app._thread.isRunning():
        return
    app.status_bar.showMessage("Statut : Exécution en cours")
    snapshot = _snapshot(app.workspace)
    thread = QThread(app)
    worker = ExecutionWorker(plan, snapshot, app.data_path.parent / "exports")
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.progress.connect(app.execution.set_progress)
    worker.log.connect(app.execution.add_log)
    app._worker = worker
    app._thread = thread
    worker.finished.connect(app._on_execution_finished, Qt.QueuedConnection)
    thread.finished.connect(thread.deleteLater)
    app.execution.reset()
    thread.start()


class _Snapshot:
    def __init__(self, data: dict) -> None:
        self.universes = {u["id"]: dict(u) for u in data.get("universes", [])}
        self.sources_by_uid = _group(data.get("sources", []), "universeId")
        self.candidates_by_uid = _group(data.get("candidates", []), "universeId")

    def get(self, uid: str):
        item = self.universes.get(uid)
        return dict(item) if item else None


def _snapshot(workspace) -> _Snapshot:
    return _Snapshot(workspace.data)


def _group(items: list[dict], key: str) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for item in items:
        grouped.setdefault(item.get(key, ""), []).append(dict(item))
    return grouped


def handle_finished(app, result) -> None:
    thread = getattr(app, "_thread", None)
    worker = getattr(app, "_worker", None)
    app.execution.finish()
    status = "Statut : Exécution terminée"
    if isinstance(result, dict) and not result.get("ok", True):
        status = "Statut : Exécution en erreur"
    if isinstance(result, dict) and result.get("ok"):
        _apply_result(app.workspace, result)
    app.status_bar.showMessage(status)
    if thread is not None:
        thread.quit()
    if worker is not None:
        worker.deleteLater()
    app._thread = None
    app._worker = None
    app.refresh_current()


def _apply_result(workspace, result: dict) -> None:
    for entry in result.get("runs", []):
        uid = entry.get("universeId")
        docs = entry.get("docs", [])
        run = entry.get("run")
        if not uid or not run:
            continue
        unchanged = [
            d for d in workspace.data.get("documents", [])
            if d.get("universeId") != uid
        ]
        current = [
            d for d in workspace.data.get("documents", [])
            if d.get("universeId") == uid
        ]
        workspace.data["documents"] = unchanged + _upsert_docs(current, docs)
        workspace.data.setdefault("runs", []).insert(0, run)
    workspace.save()


def _upsert_docs(existing: list[dict], incoming: list[dict]) -> list[dict]:
    by_key: dict[str, dict] = {}
    order: list[str] = []
    for doc in existing + incoming:
        key = str(doc.get("url") or doc.get("id") or "").strip().lower()
        if not key:
            key = f"id:{doc.get('id', '')}"
        if key not in by_key:
            order.append(key)
        by_key[key] = doc
    return [by_key[key] for key in order]
