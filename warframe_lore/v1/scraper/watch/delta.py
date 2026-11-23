"""Targeted incremental delta collection triggered by watch detections."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from ..adapters.outbound.http.client import HttpClientAdapter
from ..use_cases.apply_result import apply_result
from ..use_cases.run_universe import run_universe


class _QuietObserver:
    def progress(self, _percent: int, _step: str) -> None:
        return

    def log(self, _message: str) -> None:
        return

    def event(self, _event_type: str, **_payload: Any) -> None:
        return


def run_targeted_delta(
    workspace: Any,
    universe_id: str,
    source_ids: list[str],
    *,
    settings: Any,
    client: Any | None = None,
    collector: Any | None = None,
) -> dict[str, Any]:
    """Run an incremental delta collection limited strictly to changed sources."""
    universe = workspace.get(universe_id)
    if universe is None or not source_ids:
        return {"universe_id": universe_id, "sources": 0, "documents": 0}
    target_set = set(source_ids)
    selected = [
        dict(s) for s in workspace.sources_for(universe_id)
        if str(s.get("id", "")) in target_set
    ]
    if not selected:
        return {"universe_id": universe_id, "sources": 0, "documents": 0}
    ws_path = getattr(workspace, "path", None)
    base = ws_path.parent if isinstance(ws_path, Path) else Path("data/v1")
    caps = dict(workspace.capabilities_for(universe_id))
    snap = SimpleNamespace(
        universes={universe_id: dict(universe)},
        sources_by_uid={universe_id: selected},
        candidates_by_uid={universe_id: []},
        capabilities_by_uid={universe_id: caps},
        get=lambda uid: dict(universe) if uid == universe_id else None,
    )
    ctx = SimpleNamespace(
        client=client or HttpClientAdapter(timeout=(5.0, 15.0), max_retries=2),
        export_root=base / "exports",
        snapshot=snap,
        state={},
        observer=_QuietObserver(),
    )
    is_dc = hasattr(settings, "__dataclass_fields__")
    limits = asdict(settings) if is_dc else dict(settings)
    limits["incremental"] = True
    limits["use_cache"] = True
    formats = list(limits.get("output_formats") or ("json",))
    entry = (
        collector(ctx, universe, formats, limits)
        if collector is not None
        else run_universe(ctx, universe, formats, limits)
    )
    apply_result(workspace, {"runs": [entry]})
    for src in workspace.sources_for(universe_id):
        st = src.get("watch_state")
        if str(src.get("id", "")) in target_set and isinstance(st, dict):
            st["last_changed"] = False
    if hasattr(workspace, "save"):
        workspace.save()
    return {
        "universe_id": universe_id,
        "sources": len(selected),
        "documents": len(entry.get("docs") or []),
        "run_id": (entry.get("run") or {}).get("id", ""),
    }
