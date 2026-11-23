"""Universe watch runner persisting ETag/Last-Modified state and audit events."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from ..capabilities.models import UniverseCapabilities
from .detectors import infer_watcher_kind, watch_url_for
from .models import WatchCheckResult, WatchRunReport, WatchTarget, utc_now_iso
from .probe import probe_target

_MAX_EVENTS = 100
_WATCHABLE_STATUSES = {"approved", "active"}


def watch_targets_for(workspace: Any, universe_id: str) -> list[WatchTarget]:
    """Build WatchTargets for all active remote sources of a universe."""
    targets: list[WatchTarget] = []
    for source in workspace.sources_for(universe_id):
        if str(source.get("status", "")).lower() not in _WATCHABLE_STATUSES:
            continue
        kind = str(source.get("kind", "")).lower()
        loc = str(source.get("location", "")).strip()
        if kind == "local_directory" or not loc.startswith(("http://", "https://")):
            continue
        wkind = infer_watcher_kind(source)
        raw_st = source.get("watch_state")
        st = raw_st if isinstance(raw_st, dict) else {}
        targets.append(
            WatchTarget(
                source_id=str(source.get("id", "")),
                universe_id=universe_id,
                url=watch_url_for(source, wkind),
                watcher_kind=wkind,
                etag=str(st.get("etag", "")),
                last_modified=str(st.get("last_modified", "")),
                fingerprint=str(st.get("fingerprint", "")),
                last_checked_at=str(st.get("last_checked_at", "")),
                consecutive_errors=int(st.get("consecutive_errors", 0) or 0),
            )
        )
    return targets


def check_universe_watch(
    workspace: Any,
    universe_id: str,
    *,
    client: Any | None = None,
    force: bool = True,
) -> WatchRunReport:
    """Probe watchable sources, persist conditional state and return a report."""
    caps = UniverseCapabilities.from_dict(workspace.capabilities_for(universe_id))
    targets = watch_targets_for(workspace, universe_id)
    by_id = {str(s.get("id", "")): s for s in workspace.sources_for(universe_id)}
    results: list[WatchCheckResult] = []
    changed_ids: list[str] = []
    for target in targets:
        if not force and _is_backed_off(target, caps.watch.backoff_minutes):
            continue
        res = probe_target(target, client=client)
        results.append(res)
        if res.changed:
            changed_ids.append(target.source_id)
        if target.source_id in by_id:
            _persist_source_state(by_id[target.source_id], res)
    events = workspace.data.setdefault("watch_events", [])
    events.extend(res.to_event() for res in results)
    if len(events) > _MAX_EVENTS:
        del events[:-_MAX_EVENTS]
    if hasattr(workspace, "save"):
        workspace.save()
    return WatchRunReport(
        universe_id=universe_id,
        checked=len(results),
        changed_source_ids=changed_ids,
        results=results,
        checked_at=utc_now_iso(),
    )


def _persist_source_state(source: dict[str, Any], res: WatchCheckResult) -> None:
    raw_prev = source.get("watch_state")
    prev = raw_prev if isinstance(raw_prev, dict) else {}
    errors = int(prev.get("consecutive_errors", 0) or 0) + 1 if res.error else 0
    source["watch_state"] = {
        "watcher_kind": res.target.watcher_kind,
        "watch_url": res.target.url,
        "etag": res.new_etag or str(prev.get("etag", "")),
        "last_modified": res.new_last_modified or str(prev.get("last_modified", "")),
        "fingerprint": res.new_fingerprint or str(prev.get("fingerprint", "")),
        "last_checked_at": res.checked_at,
        "last_reason": res.reason,
        "last_changed": res.changed,
        "last_status": res.status_code,
        "detected_items": list(res.detected_items[:5]),
        "consecutive_errors": errors,
    }


def _is_backed_off(target: WatchTarget, backoff_minutes: int) -> bool:
    if target.consecutive_errors <= 0 or not target.last_checked_at:
        return False
    try:
        last = datetime.strptime(target.last_checked_at, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=UTC
        )
    except ValueError:
        return False
    mult = min(target.consecutive_errors, 4)
    wait = timedelta(minutes=max(1, backoff_minutes) * mult)
    return datetime.now(UTC) < last + wait
