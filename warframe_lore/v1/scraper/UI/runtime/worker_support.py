"""Observer adapter and limit mapping for the execution worker."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ...observability.deadline import DEFAULT_SOURCE_TIMEOUT
from ...settings import Settings

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
