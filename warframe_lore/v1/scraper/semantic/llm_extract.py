"""Budget-aware optional LLM enrichment for semantic entities and relations."""

from __future__ import annotations

import json
import re
from typing import Any

from ..ports.outbound.llm import LlmPort, LlmRequest
from .models import (
    ENTITY_TYPES,
    RELATION_TYPES,
    Entity,
    Mention,
    Relation,
    canonical_key,
    stable_id,
)

_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_PROMPT_TEMPLATE = (
    "Extract JSON with keys 'entities' ([{{name, kind, aliases}}]) and "
    "'relations' ([{{source, target, type, evidence}}]). "
    "Allowed entity kinds: person, location, faction, concept, timeline. "
    "Allowed relation types: BELONGS_TO, LOCATED_IN, ALLIED_WITH, OPPOSES, "
    "CREATED_BY, PART_OF, OCCURRED_IN, RELATED_TO. Return JSON only.\n\nText:\n{text}"
)


def enrich_chunk_with_llm(
    adapter: LlmPort,
    chunk_text: str,
    *,
    doc_id: str,
    chunk_id: str,
    url: str = "",
    taxonomy: list[str] | None = None,
    max_tokens: int = 512,
) -> tuple[list[Entity], list[Relation], list[Mention]]:
    """Run one budgeted LLM extraction call and parse validated entities/relations."""
    prompt = _PROMPT_TEMPLATE.format(text=chunk_text[:2500])
    try:
        resp = adapter.generate(LlmRequest(prompt=prompt, max_tokens=max_tokens))
    except Exception:  # noqa: BLE001
        return [], [], []
    data = _parse_json(resp.text)
    if not data:
        return [], [], []

    tax = list(taxonomy or [])
    entities: list[Entity] = []
    by_key: dict[str, Entity] = {}
    mentions: list[Mention] = []
    for raw in data.get("entities") or []:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name", "")).strip()
        kind = str(raw.get("kind", "concept")).strip().lower()
        if kind not in ENTITY_TYPES:
            kind = "concept"
        key = canonical_key(name)
        if not key or key in by_key:
            continue
        aliases = [
            str(a).strip() for a in (raw.get("aliases") or []) if str(a).strip()
        ]
        ent = Entity(
            id=stable_id("ent", kind, key),
            name=name, kind=kind, aliases=aliases, taxonomy=list(tax),
            confidence=0.85, extractor="llm",
            chunk_ids=[chunk_id], document_ids=[doc_id], mention_count=1,
        )
        by_key[key] = ent
        entities.append(ent)
        mid = stable_id("men", ent.id, chunk_id, "llm")
        mentions.append(
            Mention(mid, ent.id, name, doc_id, chunk_id, url, chunk_text[:160])
        )

    relations: list[Relation] = []
    for raw in data.get("relations") or []:
        if not isinstance(raw, dict):
            continue
        s_key = canonical_key(str(raw.get("source", "")))
        t_key = canonical_key(str(raw.get("target", "")))
        src, dst = by_key.get(s_key), by_key.get(t_key)
        if src is None or dst is None or src.id == dst.id:
            continue
        rtype = str(raw.get("type", "RELATED_TO")).strip().upper()
        if rtype not in RELATION_TYPES:
            rtype = "RELATED_TO"
        rid = stable_id("rel", src.id, dst.id, rtype, chunk_id)
        relations.append(
            Relation(
                id=rid, source_id=src.id, target_id=dst.id, relation_type=rtype,
                confidence=0.82, extractor="llm",
                evidence=str(raw.get("evidence", ""))[:200],
                document_id=doc_id, chunk_id=chunk_id, url=url,
            )
        )
    return entities, relations, mentions


def _parse_json(text: str) -> dict[str, Any]:
    raw = text.strip()
    if not raw:
        return {}
    match = _FENCE_RE.search(raw)
    if match:
        raw = match.group(1)
    try:
        parsed = json.loads(raw)
    except ValueError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
