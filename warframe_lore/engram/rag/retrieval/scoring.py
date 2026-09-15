"""Scoring and text helpers of the hybrid retrieval (pure — no database).

Single responsibility: the deterministic maths and wording helpers shared by the
two channels — exact query terms (highlighting), section label of a chunk,
ingestion-time context prefix, ``ts_rank_cd`` normalization and the transparent
score fusion.  Every value here is surfaced to the inspector: the ordering never
hides a raw score.
"""

from __future__ import annotations

import re
from typing import Any

# ts_headline output cap (PostgreSQL options string — no inner quotes).
FTS_HEADLINE_OPTIONS = "MaxWords=40, MinWords=15, MaxFragments=2"

# French lexical configuration used by the FTS channel.
FTS_CONFIG = "french"

# Fusion weights: cosine is the primary signal, full-text the lexical guard.
COSINE_WEIGHT = 0.6
FTS_WEIGHT = 0.4

_WORD = re.compile(r"[^\W\d_][\w'-]*", re.UNICODE)

# Context prefix injected at ingestion time ("Page: X | Section: Y - ..."):
# stripped from the served content, the header [page] > [section] carries it.
_CONTEXT_PREFIX = re.compile(r"^Page: [^\n]+?(?: \| Section: [^\n]*?)? - ")


def query_terms(query: str) -> list[str]:
    """Exact, deduplicated, ordered terms of the query (for highlighting).

    Keeps the raw user wording (the "exact terms" visible in the corpus) rather
    than the stemmed lexemes: matching stays faithful to the text.
    """
    seen: set[str] = set()
    terms: list[str] = []
    for token in _WORD.findall(query.casefold()):
        if len(token) >= 3 and token not in seen:
            seen.add(token)
            terms.append(token)
    return terms


def section_label(metadata: dict[str, Any]) -> str:
    """Section chain of a chunk: ``metadata["section"]`` or the heading
    hierarchy (``Header 2``..``Header 6``), skipping the page-level ``h1``."""
    section = metadata.get("section")
    if section:
        return str(section)
    titles = [str(metadata[f"Header {level}"]) for level in range(2, 7)
              if metadata.get(f"Header {level}")]
    return " > ".join(title for title in titles if title)


def strip_context_prefix(content: str) -> str:
    """Drops the ingestion-time ``Page: X | Section: Y - `` prefix."""
    return _CONTEXT_PREFIX.sub("", content, count=1).strip()


def ts_rank_normalized(ts_rank: float) -> float:
    """Maps ``ts_rank_cd`` (unbounded) frequency to 0..1 (r/(1+r))."""
    if ts_rank is None or ts_rank < 0:
        return 0.0
    return ts_rank / (1.0 + ts_rank)


def fuse(cosine: float | None, ts: float | None) -> float:
    """Weighted fusion of the normalized per-channel scores (transparent)."""
    if cosine is not None and ts is not None:
        return COSINE_WEIGHT * cosine + FTS_WEIGHT * ts
    if cosine is not None:
        return COSINE_WEIGHT * cosine
    if ts is not None:
        return FTS_WEIGHT * ts
    return 0.0


__all__ = ["COSINE_WEIGHT", "FTS_CONFIG", "FTS_HEADLINE_OPTIONS", "FTS_WEIGHT",
           "fuse", "query_terms", "section_label", "strip_context_prefix",
           "ts_rank_normalized"]
