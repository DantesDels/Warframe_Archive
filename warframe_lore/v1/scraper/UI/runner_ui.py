"""Background execution orchestration for the PySide6 UI."""

from __future__ import annotations

from PySide6.QtCore import QThread

from .worker import ExecutionWorker


def start_execution(app, plan) -> None:
    if getattr(app, "_thread", None) and app._thread.isRunning():
        return
    app.status_bar.showMessage("Statut : Exécution en cours")
    thread = QThread(app)
    worker = ExecutionWorker(plan)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.progress.connect(app.execution.set_progress)
    worker.log.connect(app.execution.add_log)
    worker.finished.connect(lambda: _on_finished(app, thread, worker))
    thread.finished.connect(thread.deleteLater)
    app._thread = thread
    app._worker = worker
    app.execution.reset()
    thread.start()


def _on_finished(app, thread, worker) -> None:
    app.execution.finish()
    app.status_bar.showMessage("Statut : Exécution terminée")
    thread.quit()
    thread.wait()
    worker.deleteLater()
    app._thread = None
    app._worker = None
