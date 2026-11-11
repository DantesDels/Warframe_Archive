"""Step-by-step RAG pipeline explainer for developers.

Single responsibility: trace a query through query sanitization, hostile probe
detection, alias expansion, search query creation, vector similarity search,
relevance floor filtering, entity lookup guard, and prompt assembly.
"""

from __future__ import annotations

from warframe_lore.engram.rag.audit import CONTEXT_PREVIEW
from warframe_lore.engram.rag.context import RAGContext
from warframe_lore.engram.rag.query.aliases import AliasResolver
from warframe_lore.engram.rag.query.probes import detect_probe
from warframe_lore.engram.rag.query.query_guard import sanitize_query
from warframe_lore.engram.rag.query.search_query import search_query
from warframe_lore.engram.rag.retrieval.relevance import (
    keep_relevant,
    missing_entity,
    relevance_floor,
)


async def explain_query(question: str, subject: str | None = None) -> int:
    """Trace ``question`` through every stage of the RAG pipeline."""
    sep = "=" * 70
    print(f"\n{sep}\nCEPHALON RAG EXPLAINER\n{sep}")
    print(f"1. Raw Question: {question!r}")
    clean = sanitize_query(question)
    print(f"2. Sanitized Question: {clean!r}")
    if not clean:
        print("   -> SHORT-CIRCUIT: Query is empty.")
        return 0
    is_probe = detect_probe(clean)
    print(f"3. Hostile Probe Detected: {is_probe}")
    if is_probe:
        print("   -> SHORT-CIRCUIT: Hostile probe detected (JAILBREAK_REJECT).")
        return 0
    expanded, alias_note, canon = AliasResolver().resolve(clean)
    print(f"4. Alias Expansion:\n   - Expanded: {expanded!r}\n"
          f"   - Canonical: {canon!r}\n   - Note: {alias_note!r}")
    standalone = await search_query(expanded, RAGContext())
    print(f"5. Embedded Search Query: {standalone!r}\n6. Retrieval & Search:")
    try:
        import asyncio

        from warframe_lore.engram.api.container import Container
        container = Container()
        call = container.llm.embed([standalone])
        vector = (await asyncio.wait_for(call, timeout=1.5))[0]
        hits = await asyncio.wait_for(
            container.rag.pipeline.retriever.search(vector), timeout=2.0)
    except Exception as exc:  # noqa: BLE001
        print(f"   [!] Retrieval offline (DB or LM Studio unreachable): {exc}")
        print("   (Ensure PostgreSQL and LM Studio on port 1234 are active)")
        print(f"{sep}\n")
        return 0
    floor = relevance_floor(container.config.suggestion_min_score,
                            container.config.critical_min_score)
    print(f"7. Relevance Filtering (Floor: {floor:.2f}):")
    for i, hit in enumerate(hits, 1):
        status = "KEPT" if hit.score >= floor else "DROPPED"
        preview = hit.content[:75].replace("\n", " ")
        print(f"   [{i}] Score: {hit.score:.4f} [{status}] | {hit.page_title}")
        print(f"       Preview: {preview}...")
    kept = keep_relevant(hits, floor)
    entity = missing_entity(clean, kept)
    print(f"8. Entity Guard:\n   - Passages Kept: {len(kept)} / {len(hits)}")
    if entity:
        print(f"   [!] Missing named entity: {entity!r} -> SHORT-CIRCUIT.")
    else:
        print("   -> Entity Guard Passed.")
    print("9. Final Decision:")
    if not kept or entity:
        suggestion = None
        if not kept:
            suggestion = await container.rag.pipeline._suggest_title(clean)
        if suggestion:
            print(f"   -> Disambiguation: « Voulez-vous dire « {suggestion} » ? »")
        else:
            print("   -> Abstention: '[Archives] Données insuffisantes...' (0 tokens)")
    else:
        prompt = container.rag.prompt_builder.build(clean, kept, alias_note=alias_note)
        preview = prompt.context[:CONTEXT_PREVIEW].replace("\n", " ")
        print(f"   -> PROMPT ASSEMBLED ({len(prompt.context)} chars context):")
        print(f"      Context: {preview}...")
    print(f"{sep}\n")
    return 0


__all__ = ["explain_query"]
