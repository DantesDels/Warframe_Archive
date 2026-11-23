"""Use case: discover candidate sources for one universe."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, cast

from ..discovery import discover


def discover_universe(
    workspace: Any,
    universe: dict[str, Any],
    settings: Any,
    *,
    client: Any | None = None,
) -> list[dict[str, Any]]:
    """Discover and persist new candidates for one universe."""
    if is_dataclass(settings) and not isinstance(settings, type):
        cfg = cast(dict[str, Any], asdict(settings))
    elif isinstance(settings, dict):
        cfg = dict(settings)
    else:
        cfg = {}
    if client is not None:
        cfg["http_client"] = client
    cfg["existing_sources"] = [
        str(src.get("location", "")).strip()
        for src in cast(
            list[dict[str, Any]], workspace.sources_for(str(universe["id"]))
        )
        if str(src.get("location", "")).strip()
    ]
    threshold = int(getattr(settings, "min_relevance", 60))
    candidates = discover(universe, threshold, settings=cfg)
    existing = {
        str(candidate.get("location", "")).rstrip("/").lower()
        for candidate in cast(
            list[dict[str, Any]], workspace.candidates_for(str(universe["id"]))
        )
    }
    new_payloads: list[dict[str, Any]] = []
    for item in candidates:
        key = item.location.rstrip("/").lower()
        if key in existing:
            continue
        existing.add(key)
        new_payloads.append(_payload(item))
    merged = [
        candidate
        for candidate in cast(
            list[dict[str, Any]], workspace.data.get("candidates", [])
        )
        if str(candidate.get("universeId")) != str(universe["id"])
    ]
    merged.extend(workspace.candidates_for(str(universe["id"])))
    merged.extend(new_payloads)
    workspace.data["candidates"] = merged
    workspace.save()
    return new_payloads


def _payload(item: Any) -> dict[str, Any]:
    return {
        "id": item.id,
        "universeId": item.universe_id,
        "kind": item.kind,
        "location": item.location,
        "title": item.title,
        "score": item.score,
        "proof": item.proof,
        "discoveredBy": item.discovered_by,
        "status": item.status,
        "forceUpdate": item.force_update,
        "scoreBreakdown": dict(item.score_breakdown),
        "metadata": dict(item.metadata),
    }
