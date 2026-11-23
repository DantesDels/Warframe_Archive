"""RAG feedback loop (KnowledgeGap ingestion, querying and curation)."""

from .ingest import gaps_jsonl_path, ingest_jsonl
from .models import (
    GAP_STATUS_LABELS,
    GAP_STATUSES,
    KnowledgeGap,
    clamp_confidence,
    normalize_question,
    priority_score,
)
from .query_builder import build_discovery_queries, discover_for_gap, extract_keywords
from .server import GapsServerHandle, start_gaps_server
from .store import (
    gaps_for,
    record_gap,
    remove_gaps,
    update_gap_status,
)

__all__ = [
    "GAP_STATUSES",
    "GAP_STATUS_LABELS",
    "GapsServerHandle",
    "KnowledgeGap",
    "build_discovery_queries",
    "clamp_confidence",
    "discover_for_gap",
    "extract_keywords",
    "gaps_for",
    "gaps_jsonl_path",
    "ingest_jsonl",
    "normalize_question",
    "priority_score",
    "record_gap",
    "remove_gaps",
    "start_gaps_server",
    "update_gap_status",
]
