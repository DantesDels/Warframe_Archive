"""Background execution worker for the desktop UI."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, cast

from PySide6.QtCore import QObject, Signal

from ..adapters.outbound.persistence.quarantine import QuarantineStore
from ..collect.cache import FetchCache
from ..collect.http import HttpClient
from ..events.log import EventLog
from ..observability.network import HTTP_TIMEOUT
from ..observability.progress import ProgressEvent, ProgressReporter
from ..security.fetch_policy import FetchPolicy
from ..settings import Settings
from ..storage import read_json, write_json
from ..use_cases.ports import UniverseRunContext
from ..use_cases.run_controls import RunControl
from ..use_cases.run_universe import run_universe
from .runtime.worker_support import (
    _WorkerObserver,
    merge_result_in_worker,
    worker_limits,
)


class ExecutionWorker(QObject):
    """Collect sources in background; UI applies results on main thread."""

    progress = Signal(int, str)
    log = Signal(str)
    finished = Signal(object)
    events_log = Signal(str, object)

    client: HttpClient
    export_root: Path
    snapshot: Any
    state: dict[str, Any]
    observer: _WorkerObserver

    def __init__(self, plan: Any, workspace_snapshot: Any, export_root: Path) -> None:
        super().__init__()
        from . import artifacts as _preload_artifacts  # noqa: F401

        self.plan = plan
        self.snapshot = workspace_snapshot
        self.export_root = Path(export_root)
        base = self.export_root.parent
        self.cache = FetchCache(base / "cache" / "http")
        self.state_path = base / "incremental_state.json"
        self.checkpoint_path = base / "run_checkpoint.json"
        self.state = cast(dict[str, Any], read_json(self.state_path, {}))
        self.events = EventLog(base / "events.jsonl")
        self.quarantine = QuarantineStore(base / "quarantine")
        self.control = RunControl()
        self.reporter = ProgressReporter(self._on_progress_event)
        self.client = HttpClient(
            timeout=HTTP_TIMEOUT, max_retries=2, cache=self.cache,
            policy=FetchPolicy(max_bytes=5_000_000), event_log=self.events,
            quarantine=self.quarantine, reporter=self.reporter, control=self.control,
        )
        self.observer = _WorkerObserver(self)
        self._progress_lock = threading.Lock()
        self._max_progress = 0

    def emit_progress(self, percent: int, message: str) -> None:
        if percent > 0:
            with self._progress_lock:
                self._max_progress = max(self._max_progress, percent)
                percent = self._max_progress
        self.progress.emit(percent, message)

    def _on_progress_event(self, event: ProgressEvent) -> None:
        self.log.emit(event.message)
        if event.percent > 0:
            self.emit_progress(event.percent, event.message)
        elif event.stage in {"http", "retry", "manifest"}:
            self.emit_progress(-1, event.message)
        if event.stage in {"source", "page", "export"}:
            self.events_log.emit(event.stage, {
                "message": event.message,
                "current": event.current,
                "total": event.total,
            })

    def pause(self) -> None:
        self.control.pause()
        self.log.emit("Exécution en pause.")
        self.events.emit("run_paused", outcome="paused")

    def resume(self) -> None:
        self.control.resume()
        self.log.emit("Exécution reprise.")
        self.events.emit("run_resumed", outcome="resumed")

    def cancel(self) -> None:
        self.control.cancel()
        self.log.emit("Exécution annulée par l'utilisateur.")
        self.events.emit("run_cancel_requested", outcome="cancelling")

    def run(self) -> None:
        try:
            self.finished.emit(self._run())
        except Exception as exc:  # noqa: BLE001
            self.log.emit(f"Erreur: {exc}")
            self.events.emit("run_failed", error=str(exc), outcome="failed")
            self.finished.emit({"ok": False, "error": str(exc), "runs": []})

    def _run(self) -> dict[str, Any]:
        settings = cast(Settings, self.plan.settings)
        limits = worker_limits(settings, self.reporter, self.control)
        formats = [str(fmt).lower() for fmt in settings.output_formats]
        runs: list[dict[str, Any]] = []
        self.events.emit(
            "run_started", universes=list(self.plan.universe_ids), actor="user"
        )
        for uid in self.plan.universe_ids:
            if self.control.is_cancelled():
                break
            universe = cast(dict[str, Any] | None, self.snapshot.get(str(uid)))
            if universe:
                ctx = cast(UniverseRunContext, self)
                runs.append(run_universe(ctx, universe, formats, limits))
        write_json(self.state_path, self.state)
        cancelled = self.control.is_cancelled() or any(
            bool(cast(dict[str, Any], run).get("cancelled")) for run in runs
        )
        result: dict[str, Any] = (
            {"ok": False, "cancelled": True, "runs": runs}
            if cancelled
            else {"ok": True, "runs": runs}
        )
        merge_result_in_worker(self.snapshot, result)
        self.progress.emit(100, "Annulé" if cancelled else "Terminé")
        evt = "run_cancelled" if cancelled else "run_finished"
        outcome = "cancelled" if cancelled else "ok"
        self.events.emit(evt, runs=len(runs), outcome=outcome)
        return result
