"""Map phase: batched LLM extraction driven by the declarative blueprint."""

from __future__ import annotations

import logging

from ..blueprint import Blueprint
from ..scraper.ports.outbound.llm import LlmPort, LlmRequest
from .documents import SourceChunk
from .models import ExtractedBatch
from .parsing import parse_extraction

logger = logging.getLogger(__name__)

_PROMPT_TEMPLATE = (
    "You extract a knowledge graph from narrative documents. Return JSON only, "
    'with keys "entities" and "relations".\n'
    'entities: [{{"name": str, "type": one of [{entity_types}], '
    '"aliases": [str], "attributes": {{}}, '
    '"facts": [{{"statement": str, "source_id": chunk id, "arc": str}}]}}]\n'
    'relations: [{{"source": entity name, "target": entity name, '
    '"type": one of [{relation_types}], "arc": str, "evolution": str, '
    '"source_id": chunk id}}]\n'
    "Every fact and relation MUST carry the source_id of the chunk it comes "
    "from. Use only the declared types. The arc field names the narrative arc "
    "or context; evolution describes how the relation changes over time.\n\n"
    "{chunks}"
)


def build_prompt(blueprint: Blueprint, chunks: list[SourceChunk]) -> str:
    """Render the extraction prompt for one batch of identified chunks."""
    blocks = [
        f"[CHUNK {chunk.chunk_id}]\n{chunk.text}\n[/CHUNK]" for chunk in chunks
    ]
    return _PROMPT_TEMPLATE.format(
        entity_types=", ".join(blueprint.entity_types),
        relation_types=", ".join(blueprint.relation_types),
        chunks="\n\n".join(blocks),
    )


def extract_batch(
    llm: LlmPort,
    blueprint: Blueprint,
    chunks: list[SourceChunk],
    *,
    max_tokens: int = 1500,
) -> ExtractedBatch | None:
    """Run one budgeted LLM call; return None when the call failed.

    A None result lets the engine keep the chunks unacknowledged so the
    next run retries them instead of caching an empty extraction.
    """
    if not chunks:
        return ExtractedBatch()
    prompt = build_prompt(blueprint, chunks)
    try:
        response = llm.generate(LlmRequest(prompt=prompt, max_tokens=max_tokens))
    except Exception:  # noqa: BLE001 - a failed batch must not stop the run
        logger.warning("LLM extraction failed for %d chunk(s)", len(chunks))
        return None
    return parse_extraction(response.text, blueprint, chunks)
