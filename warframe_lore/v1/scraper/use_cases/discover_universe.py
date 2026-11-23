"""Use case: discover candidate sources for one universe."""

from __future__ import annotations

from typing import Any, cast

from ..discovery import discover


def discover_universe(
    workspace: Any, universe: dict[str, Any], settings: Any, *,
        client: Any | None = None
) -> list[dict[str, Any]]:
    cfg = settings.__dict__.copy() if hasattr(settings, "__dict__") else {}
    if client is not None:
        cfg["http_client"] = client
    threshold = int(getattr(settings, "min_relevance", 60))
    candidates = discover(universe, threshold, settings=cfg)
    existing = {
        str(c.get("location", "")).rstrip("/").lower()
        for c in cast(list[dict[str, Any]],
            workspace.candidates_for(str(universe["id"])))
    }
    new_payloads: list[dict[str, Any]] = []
    for item in candidates:
        key = item.location.rstrip("/").lower()
        if key in existing:
            continue
        existing.add(key)
        new_payloads.append(_payload(item))
    merged = [
        c for c in cast(list[dict[str, Any]], workspace.data.get("candidates", []))
        if str(c.get("universeId")) != str(universe["id"])
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
