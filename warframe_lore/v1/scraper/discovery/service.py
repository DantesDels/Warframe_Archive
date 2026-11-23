"""Discovery orchestration: threshold filtering and deduplication."""

from __future__ import annotations

from typing import Any

from .models import Candidate
from .providers import build_default_providers
from .scoring import score_candidate


def keywords_for(name: str, description: str = "") -> list[str]:
    """Extract meaningful keywords from a Universe label and description."""
    words = [
        word.strip(" ,.;:!?()[]\"'")
        for word in f"{name} {description}".split()
    ]
    return list(dict.fromkeys(word for word in words if len(word) >= 3))[:6]


def discover(
    universe: dict[str, Any],
    min_relevance: int,
    provider: Any | None = None,
    *,
    providers: list[Any] | None = None,
    settings: dict[str, Any] | None = None,
) -> list[Candidate]:
    """Return deduplicated candidates scoring at least ``min_relevance``%."""
    cfg = settings or {}
    keywords = keywords_for(
        str(universe.get("name", "")), str(universe.get("description", ""))
    )
    active = _providers(provider, providers, cfg)
    u2 = dict(universe)
    u2["_discovery_cfg"] = cfg
    found: list[Candidate] = list(_seed_candidates(u2, cfg))
    for prov in active:
        found.extend(_search(prov, keywords, str(universe.get("id", "")), u2))
    scored = [score_candidate(item, universe, keywords) for item in found]
    kept = [item for item in scored if item.score * 100 >= min_relevance]
    deduped = _dedupe(kept)
    limit = int(cfg.get("discovery_max_candidates", 0) or 0)
    return deduped[:limit] if limit > 0 else deduped


def _seed_candidates(universe: dict[str, Any], cfg: dict[str, Any]) -> list[Candidate]:
    seeds = cfg.get("discovery_seeds", []) or []
    uid = str(universe.get("id", ""))
    out: list[Candidate] = []
    for idx, raw in enumerate(seeds):
        loc = str(raw).strip()
        if not loc:
            continue
        out.append(
            Candidate(
                id=f"seed-{idx}",
                universe_id=uid,
                kind="website",
                location=loc,
                title=loc,
                score=0.65,
                proof="Source seed configur?e",
                discovered_by="seed",
                score_breakdown={"authority": 0.6, "confidence": 0.7},
                metadata={"probe": "seed"},
            )
        )
    return out


def _providers(provider: Any | None, providers: list[Any] | None, settings: dict[str,
    Any] | None) -> list[Any]:
    if providers is not None:
        return providers
    if provider is not None:
        return [provider]
    return build_default_providers(settings or {})


def _search(provider: Any, keywords: list[str], uid: str, universe: dict[str,
    Any]) -> list[Candidate]:
    search = getattr(provider, "search", None)
    if search is None:
        return []
    cfg = universe.get("_discovery_cfg", {}) if isinstance(universe, dict) else {}
    client = cfg.get("http_client") if isinstance(cfg, dict) else None
    try:
        result = search(keywords, uid, universe=universe, client=client)
    except TypeError:
        try:
            result = search(keywords, uid, universe=universe)
        except TypeError:
            result = search(keywords, uid)
    return [item for item in result if isinstance(item, Candidate)]


def _dedupe(candidates: list[Candidate]) -> list[Candidate]:
    unique: dict[str, Candidate] = {}
    for item in sorted(candidates, key=lambda c: c.score, reverse=True):
        key = item.location.strip().lower().rstrip("/")
        if key and key not in unique:
            unique[key] = item
    return list(unique.values())
