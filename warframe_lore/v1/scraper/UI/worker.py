"""Background execution worker for the desktop UI."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from PySide6.QtCore import QObject, Signal

from ..adapters.outbound.persistence.quarantine import QuarantineStore
from ..collect.cache import FetchCache
from ..collect.http import HttpClient
from ..events.log import EventLog
from ..security.fetch_policy import FetchPolicy
from ..settings import Settings
from ..storage import read_json, write_json
from ..use_cases.ports import UniverseRunContext
from ..use_cases.run_universe import run_universe


class _WorkerObserver:
    def __init__(self, worker: ExecutionWorker) -> None:
        self.worker = worker

    def progress(self, percent: int, step: str) -> None:
        self.worker.progress.emit(percent, step)

    def log(self, message: str) -> None:
        self.worker.log.emit(message)

    def event(self, event_type: str, **payload: Any) -> None:
        self.worker.events_log.emit(event_type, payload)


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
        self.plan = plan
        self.snapshot = workspace_snapshot
        self.export_root = Path(export_root)
        base = self.export_root.parent
        self.cache = FetchCache(base / "cache" / "http")
        self.state_path = base / "incremental_state.json"
        self.state = cast(dict[str, Any], read_json(self.state_path, {}))
        self.events = EventLog(base / "events.jsonl")
        self.quarantine = QuarantineStore(base / "quarantine")
        self.client = HttpClient(
            cache=self.cache,
            policy=FetchPolicy(max_bytes=5_000_000),
            event_log=self.events,
            quarantine=self.quarantine,
        )
        self.observer = _WorkerObserver(self)

    def run(self) -> None:
        try:
            self.finished.emit(self._run())
        except Exception as exc:  # noqa: BLE001
            self.log.emit(f"Erreur: {exc}")
            self.events.emit("run_failed", error=str(exc), outcome="failed")
            self.finished.emit({"ok": False, "error": str(exc), "runs": []})

    def _run(self) -> dict[str, Any]:
        settings = cast(Settings, self.plan.settings)
        limits = _limits(settings)
        formats = [str(f).lower() for f in settings.output_formats]
        runs: list[dict[str, Any]] = []
        self.events.emit(
            "run_started", universes=list(self.plan.universe_ids), actor="user"
        )
        for uid in self.plan.universe_ids:
            universe = cast(dict[str, Any] | None, self.snapshot.get(str(uid)))
            if universe:
                runs.append(
                    run_universe(
                        cast(UniverseRunContext, self), universe, formats, limits
                    )
                )
        write_json(self.state_path, self.state)
        self.progress.emit(100, "Termin?")
        self.log.emit("Ex?cution termin?e.")
        self.events.emit("run_finished", runs=len(runs), outcome="ok")
        return {"ok": True, "runs": runs}


def _limits(settings: Settings) -> dict[str, Any]:
    return {
        "max_pages_per_source": settings.max_pages_per_source,
        "max_depth": settings.max_depth,
        "same_host_only": settings.same_host_only,
        "use_cache": settings.use_cache,
        "incremental": settings.incremental,
        "expand_manifests": settings.expand_manifests,
        "max_manifest_urls": settings.max_manifest_urls,
    }
