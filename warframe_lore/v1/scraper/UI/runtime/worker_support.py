"""Observer adapter and limit mapping for the execution worker."""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any

from ...observability.deadline import DEFAULT_SOURCE_TIMEOUT
from ...settings import Settings
from ...use_cases.apply_result import apply_result
from ...use_cases.pending_children_store import (
    MAX_PENDING_CHILDREN_PER_RUN,
    MAX_PENDING_CHILDREN_PER_SOURCE,
)
from ..workspace import WorkshopWorkspace

if TYPE_CHECKING:
    from ..worker import ExecutionWorker


class _WorkerObserver:
    def __init__(self, worker: ExecutionWorker) -> None:
        self.worker = worker

    def progress(self, percent: int, step: str) -> None:
        self.worker.emit_progress(percent, step)

    def log(self, message: str) -> None:
        self.worker.log.emit(message)

    def event(self, event_type: str, **payload: Any) -> None:
        self.worker.events_log.emit(event_type, payload)


def worker_limits(
    settings: Settings, reporter: Any, control: Any
) -> dict[str, Any]:
    """Build the generic limits mapping passed to all use cases."""
    return {
        "max_pages_per_source": settings.max_pages_per_source,
        "max_depth": settings.max_depth,
        "same_host_only": settings.same_host_only,
        "use_cache": settings.use_cache,
        "incremental": settings.incremental,
        "expand_manifests": settings.expand_manifests,
        "max_manifest_urls": settings.max_manifest_urls,
        "max_pending_children_per_source": getattr(
            settings, "max_pending_children_per_source", MAX_PENDING_CHILDREN_PER_SOURCE
        ),
        "max_pending_children_per_run": getattr(
            settings, "max_pending_children_per_run", MAX_PENDING_CHILDREN_PER_RUN
        ),
        "allowed_languages": getattr(settings, "allowed_languages", ("en",)),
        "review_child_pages": settings.review_child_pages,
        "use_playwright": settings.use_playwright,
        "rag_coupling": settings.rag_coupling,
        "max_concurrency": settings.max_concurrency,
        "per_host_concurrency": settings.per_host_concurrency,
        "per_host_delay": settings.per_host_delay,
        "max_retries": settings.max_retries,
        "graph_enabled": settings.graph_enabled,
        "source_timeout_seconds": DEFAULT_SOURCE_TIMEOUT,
        "reporter": reporter,
        "control": control,
    }


def merge_result_in_worker(snapshot: Any, result: dict[str, Any]) -> None:
    """Merge and persist execution results off the Qt main thread."""
    raw = getattr(snapshot, "raw_data", None)
    if not isinstance(raw, dict):
        return
    if not (result.get("ok") or result.get("cancelled")):
        return
    ws_path = getattr(snapshot, "workspace_path", None)
    worker_ws = WorkshopWorkspace(data=deepcopy(raw), path=ws_path)
    apply_result(worker_ws, result)
    result["merged_workspace_data"] = worker_ws.data
