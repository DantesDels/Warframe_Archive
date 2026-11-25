"""Authority and topic-aware scoring for child pages discovered from a parent source."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from ..collect.crawl_filter import is_generalist_domain, matches_universe_topic


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def _norm(url: str) -> str:
    return url.strip().rstrip("/").lower()


def universe_keywords(workspace: Any, universe_id: str) -> list[str]:
    """Return distinctive topic keywords for ``universe_id`` from workspace state."""
    tokens: list[str] = []
    uni = workspace.get(universe_id) if hasattr(workspace, "get") else None
    if isinstance(uni, dict):
        for field in ("name", "slug", "id"):
            raw = str(uni.get(field, "")).strip()
            for word in raw.replace("-", " ").replace("_", " ").split():
                clean = word.strip(" ,.;:!?()[]\"'").lower()
                if len(clean) >= 3 and clean not in tokens:
                    tokens.append(clean)
    if not tokens and len(universe_id.strip()) >= 3:
        for word in universe_id.replace("-", " ").replace("_", " ").split():
            if len(word) >= 3 and word.lower() not in tokens:
                tokens.append(word.lower())
    if hasattr(workspace, "capabilities_for"):
        caps = workspace.capabilities_for(universe_id)
        crawl = caps.get("crawl") if isinstance(caps, dict) else {}
        tags = crawl.get("topic_tags") if isinstance(crawl, dict) else []
        for tag in tags or []:
            t = str(tag).strip().lower()
            if len(t) >= 3 and t not in tokens:
                tokens.append(t)
    return tokens


def child_authority_score(
    workspace: Any,
    universe_id: str,
    parent_url: str,
    child_url: str,
    child_title: str = "",
) -> tuple[float, dict[str, float]]:
    """Compute a child candidate score without blind inheritance on generalist hosts."""
    parent_host = _host(parent_url)
    child_host = _host(child_url)
    same_host = bool(parent_host and child_host and parent_host == child_host)
    keywords = universe_keywords(workspace, universe_id)
    generalist = is_generalist_domain(parent_url) or is_generalist_domain(child_url)
    on_topic = matches_universe_topic(child_url, child_title, keywords)

    if generalist:
        if not on_topic:
            return 0.05, {
                "parent_authority": 0.0, "topic_match": 0.0, "confidence": 0.05,
            }
        return 0.72, {"parent_authority": 0.5, "topic_match": 1.0, "confidence": 0.72}
    if not same_host and not on_topic:
        return 0.08, {"parent_authority": 0.0, "same_host": 0.0, "confidence": 0.08}

    parent_norm = _norm(parent_url)
    sources = (
        workspace.sources_for(universe_id)
        if hasattr(workspace, "sources_for")
        else []
    )
    cands = (
        workspace.candidates_for(universe_id)
        if hasattr(workspace, "candidates_for")
        else []
    )
    source_score = _best_score(sources, parent_norm, parent_host, approved_only=True)
    cand_score = _best_score(cands, parent_norm, parent_host, approved_only=False)

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
            val = val / 100.0 if val > 1.0 else val
            val = max(0.0, min(1.0, val))
            if best is None or val > best:
                best = val
    return best
