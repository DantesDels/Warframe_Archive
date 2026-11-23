"""Human-in-the-loop child page/manifest review."""

from __future__ import annotations

from typing import Any, cast

from ..collect.http import HttpClient
from ..collect.manifest import extract_manifest_urls
from ..discovery.models import Candidate


def preview_child_candidates(
    workspace: Any,
    universe: dict[str, Any],
    location: str,
    *,
    client: Any | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    http = client or HttpClient()
    resp = http.get(location, use_cache=True)
    body = bytes(getattr(resp, "content", b""))
    text = body.decode(getattr(resp, "encoding", None) or "utf-8", errors="replace")
    urls = extract_manifest_urls(text, str(getattr(resp, "url", location)), limit=limit)
    existing = {
        str(c.get("location", "")).rstrip("/").lower()
        for c in cast(list[dict[str, Any]],
            workspace.candidates_for(str(universe["id"])))
    }
    out: list[dict[str, Any]] = []
    for idx, url in enumerate(urls):
        key = url.rstrip("/").lower()
        if key in existing:
            continue
        existing.add(key)
        cand = Candidate(
            id=f"child-{abs(hash((universe['id'], key, idx))) % 1000000}",
            universe_id=str(universe["id"]),
            kind="website",
            location=url,
            title=f"Page enfant: {url.rsplit('/', 1)[-1] or url}",
            score=0.5,
            proof=f"Page enfant détectée depuis {location}",
            discovered_by="manifest_review",
            status="proposed",
            score_breakdown={"confidence": 0.5},
            metadata={"parent_location": location, "needs_review": True},
        )
        payload = _payload(cand)
        out.append(payload)
    if out:
        merged = cast(list[dict[str, Any]], workspace.data.get("candidates", []))
        merged.extend(out)
        workspace.data["candidates"] = merged
        workspace.save()
    return out


def _payload(item: Candidate) -> dict[str, Any]:
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
