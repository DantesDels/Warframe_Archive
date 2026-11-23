"""Event-driven conditional watching and targeted delta updates (Phase P2-A)."""

from .delta import run_targeted_delta
from .detectors import extract_change_fingerprint, infer_watcher_kind, watch_url_for
from .models import WatchCheckResult, WatchRunReport, WatchTarget
from .probe import probe_target
from .scheduler import LocalWatchScheduler, check_universe_watch, watch_targets_for

__all__ = [
    "LocalWatchScheduler",
    "WatchCheckResult",
    "WatchRunReport",
    "WatchTarget",
    "check_universe_watch",
    "extract_change_fingerprint",
    "infer_watcher_kind",
    "probe_target",
    "run_targeted_delta",
    "watch_targets_for",
    "watch_url_for",
]
