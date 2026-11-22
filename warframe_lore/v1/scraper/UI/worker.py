"""Background execution worker for the desktop UI."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from ..collect.http import HttpClient
from .artifacts import emit_artifacts
from .collect import collect_source


class ExecutionWorker(QObject):
    """Collect sources in background; UI applies results on main thread."""

    progress = Signal(int, str)
    log = Signal(str)
    finished = Signal(object)

    def __init__(self, plan, workspace_snapshot, export_root: Path) -> None:
        super().__init__()
        self.plan = plan
        self.snapshot = workspace_snapshot
        self.export_root = Path(export_root)
        self.client = HttpClient()

    def run(self) -> None:
        try:
            self.finished.emit(self._run())
        except Exception as exc:  # noqa: BLE001
            self.log.emit(f"Erreur: {exc}")
            self.finished.emit({"ok": False, "error": str(exc), "runs": []})

    def _run(self) -> dict:
        settings = self.plan.settings
        formats = [f.lower() for f in settings.output_formats]
        limits = {
            "max_pages_per_source": settings.max_pages_per_source,
            "max_depth": settings.max_depth,
            "same_host_only": settings.same_host_only,
        }
        runs = []
        for uid in self.plan.universe_ids:
            universe = self.snapshot.get(uid)
            if universe:
                runs.append(self._run_universe(universe, formats, limits))
        self.progress.emit(100, "TerminÃ©")
        self.log.emit("ExÃ©cution terminÃ©e.")
        return {"ok": True, "runs": runs}

    def _run_universe(self, universe: dict, formats: list[str], limits: dict) -> dict:
        uid = universe["id"]
        sources = self._active_sources(uid)
        self.log.emit(f"[{universe['name']}] {len(sources)} source(s) active(s)")
        docs, errors = self._collect_sources(sources, uid, limits)
        run = self._build_run(universe, docs, formats, errors)
        out_dir = self.export_root / uid / run["id"]
        emit_artifacts(out_dir, universe, docs, formats)
        self.log.emit(f"Artefacts exportÃ©s: {out_dir}")
        return {"universeId": uid, "docs": docs, "run": run}

    def _active_sources(self, uid: str) -> list[dict]:
        allowed = {"approved", "active"}
        return [
            s for s in self.snapshot.sources_by_uid.get(uid, [])
            if s.get("status") in allowed or s.get("selected")
        ]

    def _collect_sources(
        self, sources: list[dict], uid: str, limits: dict
    ) -> tuple[list[dict], list[str]]:
        docs, errors = [], []
        for idx, source in enumerate(sources, start=1):
            pct = min(95, int(idx / max(len(sources), 1) * 80))
            loc = str(source.get("location", ""))[:40]
            self.progress.emit(pct, f"Collecte: {loc}")
            new_docs, errs = collect_source(source, uid, self.client, limits)
            docs.extend(new_docs)
            for doc in new_docs:
                self.log.emit(f"CollectÃ©: {doc['title']}")
            for err in errs:
                errors.append(err)
                self.log.emit(f"Avertissement: {err}")
            time.sleep(0.01)
        return docs, errors

    def _build_run(
        self, universe: dict, docs: list[dict], formats: list[str], errors: list[str]
    ) -> dict:
        now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        run_id = f"run-{universe['id']}-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
        uid = universe["id"]
        counts = {
            "discovered": len(self.snapshot.candidates_by_uid.get(uid, [])),
            "approved": len(self.snapshot.sources_by_uid.get(uid, [])),
            "fetched": len(docs),
            "sorted": len(docs),
            "emitted": len(docs),
        }
        return {
            "id": run_id,
            "universeIds": [uid],
            "startedAt": now,
            "status": "done" if docs or not errors else "failed",
            "counts": counts,
            "formats": formats,
            "sinks": [
                {"name": f.upper(), "count": len(docs), "status": "done"}
                for f in formats
            ],
            "errors": errors,
        }
