"""Stage 2: declarative knowledge graph engine (Map-Reduce + analysis)."""

from __future__ import annotations

from .analysis import analyze
from .consolidation import consolidate
from .documents import SourceChunk, load_chunks
from .engine import GraphEngine
from .extraction import extract_batch
from .graph import Community, GraphAnalysis, KnowledgeGraph
from .json_store import JsonGraphStore
from .models import Entity, ExtractedBatch, Fact, Relation, SourceExcerpt
from .ports import GraphStorePort, LlmPort, LlmRequest, LlmResponse

__all__ = [
    "Community",
    "Entity",
    "ExtractedBatch",
    "Fact",
    "GraphAnalysis",
    "GraphEngine",
    "GraphStorePort",
    "JsonGraphStore",
    "KnowledgeGraph",
    "LlmPort",
    "LlmRequest",
    "LlmResponse",
    "Relation",
    "SourceChunk",
    "SourceExcerpt",
    "analyze",
    "consolidate",
    "extract_batch",
    "load_chunks",
]
