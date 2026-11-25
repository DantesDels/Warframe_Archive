"""Deterministic FR/EN rule extractor for taxonomy, entities and timelines."""

from __future__ import annotations

import re
from typing import Any

from .models import Entity, Mention, Relation, canonical_key, stable_id
from .noise import clean_entity_surface, is_noisy_entity
from .patterns import (
    ALIAS_RE,
    KIND_CLUES,
    PROPER_NOUN_RE,
    TIMELINE_RE,
)
from .relations import extract_relations

_MAX_ENTITIES_PER_CHUNK = 18
_CLUE_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    kind: tuple(
        re.compile(rf"\b{re.escape(clue)}\b", re.IGNORECASE) for clue in clues
    )
    for kind, clues in KIND_CLUES.items()
}


def extract_chunk_rules(
    chunk_text: str,
    *,
    doc_id: str,
    chunk_id: str,
    url: str = "",
    doc_title: str = "",
    taxonomy: list[str] | None = None,
) -> tuple[list[Entity], list[Relation], list[Mention]]:
    """Extract entities, aliases, timelines, mentions and relations from a chunk."""
    tax = list(taxonomy or [])
    alias_map = _extract_aliases(chunk_text)
    entities_by_key: dict[str, Entity] = {}
    mentions: list[Mention] = []

    def _add(surface: str, kind: str, excerpt: str, conf: float = 0.72) -> None:
        clean = clean_entity_surface(surface)
        key = canonical_key(clean)
        if is_noisy_entity(clean, key, kind):
            return
        if key not in entities_by_key:
            if len(entities_by_key) >= _MAX_ENTITIES_PER_CHUNK:
                return
            entities_by_key[key] = Entity(
                id=stable_id("ent", kind, key),
                name=clean,
                kind=kind,
                aliases=list(alias_map.get(key, ())),
                taxonomy=list(tax),
                confidence=conf,
                extractor="rules",
                chunk_ids=[chunk_id],
                document_ids=[doc_id],
                mention_count=1,
            )
        else:
            entities_by_key[key].mention_count += 1
        ent = entities_by_key[key]
        mid = stable_id("men", ent.id, chunk_id, str(len(mentions)))
        mentions.append(
            Mention(mid, ent.id, clean, doc_id, chunk_id, url, excerpt[:180])
        )

    if doc_title:
        _add(doc_title, _classify(doc_title, chunk_text[:160]), doc_title, conf=0.88)
    for match in TIMELINE_RE.finditer(chunk_text):
        win = _window(chunk_text, match.start(), match.end())
        _add(match.group(1), "timeline", win, conf=0.8)
    for match in PROPER_NOUN_RE.finditer(chunk_text):
        surface = match.group(1)
        win = _window(chunk_text, match.start(), match.end(), pad=42)
        _add(surface, _classify(surface, win), win, conf=0.72)

    ents = list(entities_by_key.values())
    rels = extract_relations(chunk_text, ents, doc_id, chunk_id, url)
    return ents, rels, mentions


def _extract_aliases(text: str) -> dict[str, list[str]]:
    aliases: dict[str, list[str]] = {}
    for match in ALIAS_RE.finditer(text):
        primary = clean_entity_surface(match.group(1))
        alt = clean_entity_surface(match.group(2) or match.group(3) or "")
        pkey = canonical_key(primary)
        if pkey and alt and canonical_key(alt) != pkey:
            bucket = aliases.setdefault(pkey, [])
            if alt not in bucket:
                bucket.append(alt)
    return aliases


def _classify(surface: str, context: str) -> str:
    best_kind, best_hits = "concept", 0
    for kind, patterns in _CLUE_PATTERNS.items():
        surface_hits = sum(3 for pat in patterns if pat.search(surface))
        ctx_hits = sum(1 for pat in patterns if pat.search(context))
        hits = surface_hits + ctx_hits
        if hits > best_hits:
            best_kind, best_hits = kind, hits
    return best_kind


def _window(text: str, start: int, end: int, pad: int = 70) -> str:
    return " ".join(text[max(0, start - pad) : min(len(text), end + pad)].split())


def doc_taxonomy(doc: dict[str, Any], section: str = "") -> list[str]:
    """Build clean taxonomy tags from document category, type and section."""
    parts = [
        str(doc.get("category") or "").strip(),
        str(doc.get("docType") or "").strip(),
        section.strip(),
    ]
    return list(dict.fromkeys(p for p in parts if p))
