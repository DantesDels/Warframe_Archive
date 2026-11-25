"""GraphEngine: incremental Map-Reduce orchestration over a run export."""

from __future__ import annotations

import logging
from pathlib import Path

from ..blueprint import Blueprint
from ..scraper.ports.outbound.llm import LlmPort
from .analysis import analyze
from .consolidation import consolidate
from .documents import SourceChunk, load_chunks, load_document_titles, verify_manifest
from .extraction import extract_batch
from .graph import KnowledgeGraph
from .models import ExtractedBatch, SourceExcerpt
from .ports import GraphStorePort

logger = logging.getLogger(__name__)


class GraphEngine:
    """Map chunks through the LLM port, reduce and analyze the graph.

    The Map cache plus the content-hash manifest make runs resumable:
    unchanged chunks are never sent to the LLM again, and the Reduce
    phase replays cached extractions without any model call.
    """

    def __init__(
        self,
        blueprint: Blueprint,
        llm: LlmPort,
        store: GraphStorePort,
        *,
        batch_size: int = 3,
    ) -> None:
        self.blueprint = blueprint
        self.llm = llm
        self.store = store
        self.batch_size = max(1, batch_size)

    def _cached_batch(
        self, chunk: SourceChunk, current: dict[str, str], manifest: dict[str, str]
    ) -> ExtractedBatch | None:
        if manifest.get(chunk.chunk_id) != current[chunk.chunk_id]:
            return None
        cached = self.store.load_extraction(chunk.chunk_id)
        if cached is None:
            return None
        # A cached batch is only replayable while ALL its member chunks
        # are still present and unchanged; otherwise it is re-extracted.
        if all(current.get(cid) == manifest.get(cid) for cid in cached.chunk_ids):
            return cached
        return None

    def run(self, export_dir: Path | str) -> KnowledgeGraph:
        """Build or update the knowledge graph from one Scraper v1 export."""
        export_path = Path(export_dir)
        verify_manifest(export_path)
        chunks = load_chunks(export_path)
        titles = load_document_titles(export_path)
        current = {chunk.chunk_id: chunk.content_hash() for chunk in chunks}
        manifest = self.store.load_manifest()
        batches: list[ExtractedBatch] = []
        seen: set[tuple[str, ...]] = set()
        pending: list[SourceChunk] = []
        acknowledged: dict[str, str] = {}
        for chunk in chunks:
            cached = self._cached_batch(chunk, current, manifest)
            if cached is not None:
                key = tuple(sorted(cached.chunk_ids))
                if key not in seen:
                    seen.add(key)
                    batches.append(cached)
                acknowledged[chunk.chunk_id] = current[chunk.chunk_id]
            else:
                pending.append(chunk)
        for start in range(0, len(pending), self.batch_size):
            batch_chunks = pending[start : start + self.batch_size]
            batch = extract_batch(self.llm, self.blueprint, batch_chunks)
            if batch is None:
                continue
            for chunk in batch_chunks:
                self.store.save_extraction(chunk.chunk_id, batch)
                acknowledged[chunk.chunk_id] = current[chunk.chunk_id]
            batches.append(batch)
            self.store.save_manifest(acknowledged)
        sources = {
            chunk.chunk_id: SourceExcerpt(
                text=chunk.text,
                url=chunk.url,
                document_title=titles.get(chunk.document_id, chunk.document_id),
                source_id=chunk.source_id,
            )
            for chunk in chunks
        }
        graph = consolidate(batches, sources)
        graph.analysis = analyze(graph)
        self.store.save_graph(graph)
        self.store.save_manifest(acknowledged)
        logger.info(
            "Graph built: %d entities, %d relations, %d chunk(s) re-extracted",
            len(graph.entities),
            len(graph.relations),
            len(pending),
        )
        return graph
