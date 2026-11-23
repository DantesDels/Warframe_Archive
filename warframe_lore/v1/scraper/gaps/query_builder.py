"""Transform KnowledgeGaps into targeted multi-universe discovery queries."""

from __future__ import annotations

import dataclasses
import re
from typing import Any

from ..discovery import discover
from .models import KnowledgeGap, utc_now_iso

_WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9_-]{3,}")
_STOPWORDS = frozenset({
    "les", "des", "une", "dans", "pour", "avec", "sur", "par", "est", "sont",
    "qui", "que", "quoi", "quel", "quelle", "quels", "quelles", "comment",
    "pourquoi", "quand", "elle", "ils", "elles", "mais", "donc", "entre",
    "cette", "cet", "ces", "tout", "tous", "plus", "sans", "être", "avoir",
    "the", "and", "for", "with", "from", "that", "this", "what", "who",
    "where", "when", "why", "how", "are", "was", "were", "does", "did",
    "about", "into", "their", "there", "which", "have", "has", "can",
})


def extract_keywords(question: str, universe_name: str = "") -> list[str]:
    """Extract ordered unique domain keywords from a natural-language question."""
    uni_words = {w.casefold() for w in _WORD_RE.findall(universe_name)}
    seen: set[str] = set()
    keywords: list[str] = []
    for token in _WORD_RE.findall(question):
        key = token.casefold()
        if key in _STOPWORDS or key in uni_words or key in seen:
            continue
        seen.add(key)
        keywords.append(token)
    return keywords[:8]


def build_discovery_queries(question: str, universe_name: str = "") -> list[str]:
    """Generate 2-3 focused search/discovery queries for one KnowledgeGap."""
    keywords = extract_keywords(question, universe_name)
    prefix = universe_name.strip()
    if not keywords:
        base = question.strip()[:80]
        return [f"{prefix} {base}".strip()] if base else ([prefix] if prefix else [])
    core = " ".join(keywords[:4])
    queries = [f"{prefix} {core}".strip()]
    if len(keywords) >= 2:
        queries.append(f"{prefix} {keywords[0]} {keywords[1]} wiki".strip())
    if len(keywords) > 4:
        tail = " ".join(keywords[2:6])
        queries.append(f"{prefix} {tail}".strip())
    return list(dict.fromkeys(q for q in queries if q))


def discover_for_gap(
    workspace: Any,
    gap: KnowledgeGap,
    settings: Any,
    *,
    discover_fn: Any | None = None,
) -> list[dict[str, Any]]:
    """Run targeted discovery for a KnowledgeGap and merge new candidates."""
    universe = workspace.get(gap.universe_id)
    if universe is None:
        return []
    name = str(universe.get("name", gap.universe_id))
    queries = gap.suggested_queries or build_discovery_queries(gap.question, name)
    primary = queries[0] if queries else name
    cfg = (
        dataclasses.asdict(settings)
        if dataclasses.is_dataclass(settings)
        else dict(settings or {})
    )
    runner = discover_fn or discover
    probe_universe = {**universe, "name": primary}
    candidates = runner(
        probe_universe,
        min_relevance=max(30, int(cfg.get("min_relevance", 60)) - 15),
        settings=cfg,
        existing_sources=workspace.sources_for(gap.universe_id),
    )
    existing = workspace.data.setdefault("candidates", [])
    known_locs = {
        str(c.get("location", "")).strip()
        for c in existing
        if str(c.get("universeId", "")) == gap.universe_id
    }
    added: list[dict[str, Any]] = []
    proof_prefix = f"Lacune ({gap.question[:48]})"
    for cand in candidates:
        loc = str(getattr(cand, "location", "")).strip()
        if not loc or loc in known_locs:
            continue
        known_locs.add(loc)
        record = {
            "id": str(getattr(cand, "id", "")),
            "universeId": gap.universe_id,
            "kind": str(getattr(cand, "kind", "website")),
            "location": loc,
            "title": str(getattr(cand, "title", loc)),
            "score": float(getattr(cand, "score", 0.5)),
            "proof": f"{proof_prefix} · {getattr(cand, 'proof', '')}",
            "discoveredBy": str(getattr(cand, "discovered_by", "gap")),
            "status": "proposed",
            "forceUpdate": False,
            "scoreBreakdown": dict(getattr(cand, "score_breakdown", {}) or {}),
            "metadata": {"gap_id": gap.id, "query": primary},
        }
        existing.append(record)
        added.append(record)
    for item in workspace.data.setdefault("knowledge_gaps", []):
        if str(item.get("id", "")) == gap.id:
            item["status"] = "approved"
            item["suggested_queries"] = queries
            item["updated_at"] = utc_now_iso()
            break
    if hasattr(workspace, "save"):
        workspace.save()
    return added
