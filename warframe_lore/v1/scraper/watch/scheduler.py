"""Cooperative local background scheduler for event-driven universe watching."""

from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from ..capabilities.models import UniverseCapabilities
from .models import WatchRunReport
from .runner import check_universe_watch, watch_targets_for

__all__ = ["LocalWatchScheduler", "check_universe_watch", "watch_targets_for"]


class LocalWatchScheduler:
    """Background daemon scheduler polling universes where watch.enabled is True."""

    def __init__(
        self,
        workspace: Any,
        *,
        on_changes: Callable[[str, WatchRunReport], None] | None = None,
        client: Any | None = None,
        tick_seconds: float = 30.0,
    ) -> None:
        self.workspace = workspace
        self.on_changes = on_changes
        self.client = client
        self.tick_seconds = max(0.5, float(tick_seconds))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_poll: dict[str, datetime] = {}

    def start(self) -> None:
        """Start the daemon scheduler loop if not already running."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Signal the scheduler to exit and wait briefly for thread join."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    def poll_due_once(self) -> list[WatchRunReport]:
        """Run one watch pass for every enabled universe whose interval elapsed."""
        reports: list[WatchRunReport] = []
        now = datetime.now(UTC)
        for universe in list(self.workspace.universes()):
            uid = str(universe.get("id", ""))
            caps = UniverseCapabilities.from_dict(self.workspace.capabilities_for(uid))
            if not caps.watch.enabled:
                continue
            prev = self._last_poll.get(uid)
            interval = timedelta(minutes=max(1, caps.watch.poll_minutes))
            if prev is not None and now - prev < interval:
                continue
            self._last_poll[uid] = now
            report = check_universe_watch(
                self.workspace, uid, client=self.client, force=False
            )
            reports.append(report)
            if report.changed_source_ids and self.on_changes is not None:
                self.on_changes(uid, report)
        return reports

    def _loop(self) -> None:
        while not self._stop.wait(self.tick_seconds):
            try:
                self.poll_due_once()
            except Exception:  # noqa: BLE001
                continue
