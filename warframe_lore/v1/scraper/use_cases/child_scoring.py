"""Authority-inheriting scoring for child pages discovered from a parent source."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def _norm(url: str) -> str:
    return url.strip().rstrip("/").lower()


def child_authority_score(
    workspace: Any,
    universe_id: str,
    parent_url: str,
    child_url: str,
) -> tuple[float, dict[str, float]]:
    """Compute a child candidate score weighted by its parent domain authority.

    Official/approved parent domains pass most of their authority down to same-host
    child pages so they are not dropped below typical relevance thresholds (60%).
    """
    parent_host = _host(parent_url)
    child_host = _host(child_url)
    same_host = bool(parent_host and child_host and parent_host == child_host)
    parent_norm = _norm(parent_url)

    source_score = _best_score(
        workspace.sources_for(universe_id) if hasattr(workspace, "sources_for") else [],
        parent_norm,
        parent_host,
        approved_only=True,
    )
    cand_score = _best_score(
        workspace.candidates_for(universe_id)
        if hasattr(workspace, "candidates_for")
        else [],
        parent_norm,
        parent_host,
        approved_only=False,
    )

    if source_score is not None:
        base = max(0.85, source_score)
        score = round(min(0.98, base * 0.92), 2) if same_host else 0.55
    elif cand_score is not None:
        base = max(0.65, cand_score)
        score = round(min(0.95, base * 0.92), 2) if same_host else 0.5
    else:
        base = 0.7 if same_host else 0.5
        score = 0.65 if same_host else 0.5

    breakdown = {
        "parent_authority": round(base, 2),
        "same_host": 1.0 if same_host else 0.0,
        "confidence": score,
    }
    return score, breakdown


def _best_score(
    items: list[dict[str, Any]],
    parent_norm: str,
    parent_host: str,
    *,
    approved_only: bool,
) -> float | None:
    best: float | None = None
    for item in items:
        status = str(item.get("status", "")).lower()
        if approved_only and status not in {"approved", "active"}:
            continue
        loc = str(item.get("location", ""))
        if _norm(loc) == parent_norm or (parent_host and _host(loc) == parent_host):
            try:
                val = float(item.get("score", 0.85) or 0.85)
            except (TypeError, ValueError):
                val = 0.85
            if val > 1.0:
                val = val / 100.0
            val = max(0.0, min(1.0, val))
            if best is None or val > best:
                best = val
    return best
