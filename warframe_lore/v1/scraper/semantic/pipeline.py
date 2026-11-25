"""End-to-end semantic extraction pipeline with blob hydration and provenance."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from ..capabilities.models import LlmBudget, UniverseCapabilities
from ..ports.outbound.llm import LlmPort
from ..UI.runtime.rag_chunks import iter_doc_chunks
from .aliases import resolve_aliases
from .llm_extract import enrich_chunk_with_llm
from .models import Entity, Mention, Relation, SemanticBundle
from .noise import prune_corpus_entities
from .rules import doc_taxonomy, extract_chunk_rules
from .runtime_helpers import can_call_llm, hydrate_doc, resolve_llm_adapter


def extract_docs_semantics(
    docs: list[dict[str, Any]],
    universe_id: str,
    *,
    blob_root: Path | None = None,
    llm_budget: LlmBudget | dict[str, Any] | None = None,
    llm_adapter: LlmPort | None = None,
    max_docs: int = 500,
) -> SemanticBundle:
    """Extract entities, typed relations and chunk provenance from documents."""
    adapter = resolve_llm_adapter(llm_budget, llm_adapter)
    all_ents: list[Entity] = []
    all_rels: list[Relation] = []
    all_mens: list[Mention] = []
    tax_counts: Counter[str] = Counter()
    chunk_count = 0
    selected = docs[:max_docs]

    for doc in selected:
        hydrated = hydrate_doc(doc, blob_root)
        doc_id = str(hydrated.get("id") or "doc")
        url = str(hydrated.get("url") or "")
        title = str(hydrated.get("title") or "")
        for idx, (chunk, section) in enumerate(iter_doc_chunks(hydrated)):
            if not chunk.strip():
                continue
            chunk_count += 1
            chunk_id = f"{doc_id}::{idx}"
            tax = doc_taxonomy(hydrated, section)
            tax_counts.update(tax)
            ents, rels, mens = extract_chunk_rules(
                chunk,
                doc_id=doc_id,
                chunk_id=chunk_id,
                url=url,
                doc_title=title if idx == 0 else "",
                taxonomy=tax,
            )
            all_ents.extend(ents)
            all_rels.extend(rels)
            all_mens.extend(mens)
            if adapter is not None and can_call_llm(adapter):
                l_ents, l_rels, l_mens = enrich_chunk_with_llm(
                    adapter, chunk, doc_id=doc_id, chunk_id=chunk_id,
                    url=url, taxonomy=tax,
                )
                all_ents.extend(l_ents)
                all_rels.extend(l_rels)
                all_mens.extend(l_mens)

    entities, relations, mentions = resolve_aliases(all_ents, all_rels, all_mens)
    entities, relations, mentions = prune_corpus_entities(
        entities, relations, mentions, len(selected)
    )
    stats = {
        "document_count": len(selected),
        "chunk_count": chunk_count,
        "entity_count": len(entities),
        "relation_count": len(relations),
        "mention_count": len(mentions),
        "llm_calls": int(getattr(adapter, "calls", 0)) if adapter else 0,
        "llm_tokens": int(getattr(adapter, "tokens_used", 0)) if adapter else 0,
    }
    return SemanticBundle(
        universe_id=universe_id,
        entities=entities,
        relations=relations,
        mentions=mentions,
        taxonomy=dict(tax_counts.most_common(50)),
        stats=stats,
    )


def extract_universe_semantics(
    workspace: Any,
    universe_id: str,
    *,
    max_docs: int = 500,
    llm_adapter: LlmPort | None = None,
    persist: bool = True,
) -> SemanticBundle:
    """Run semantic extraction for one universe in the workspace."""
    docs = [
        d for d in workspace.data.get("documents", [])
        if d.get("universeId") == universe_id
    ]
    caps = UniverseCapabilities.from_dict(
        workspace.data.get("capabilities", {}).get(universe_id)
    )
    ws_path = getattr(workspace, "path", None)
    blob_root = ws_path.parent if isinstance(ws_path, Path) else None
    bundle = extract_docs_semantics(
        docs, universe_id, blob_root=blob_root,
        llm_budget=caps.graph_rag, llm_adapter=llm_adapter, max_docs=max_docs,
    )
    if persist:
        workspace.data.setdefault("knowledge_graphs", {})[universe_id] = (
            bundle.to_dict()
        )
        if hasattr(workspace, "save"):
            workspace.save()
    return bundle
