"""pgvector HNSW session tuning shared by every retriever.

:func:`set_hnsw_ef_search` widens the index scan pool for the CURRENT
transaction; the default target is read once from the environment and reused
by :class:`CosinusSearch`, :class:`StructuredSearch` and the hybrid channel.
Hosted here so :mod:`search`, :mod:`structured_search`, :mod:`hybrid` and the
dossier module all share ONE source of truth without import cycles.
"""

from __future__ import annotations

import os

from sqlalchemy import text

# HNSW recall: the index scans ef_search candidates per probe (default 40).
# On a large corpus (~1000+ pages x ~30 chunks) with top_k=3 the default is
# too tight — the pool is widened here, per query (session GUC, COST: 40).
HNSW_EF_SEARCH = int(os.getenv("ENGRAM_HNSW_EF", "200"))


async def set_hnsw_ef_search(session, ef: int = HNSW_EF_SEARCH) -> None:
    """Widens the pgvector HNSW scan pool for the CURRENT transaction.

    ``hnsw.ef_search`` is the index parameter that caps how many candidates
    are scanned per probe (default 40).  Raised here per query so a growing
    corpus keeps its recall without rebuilding the index.
    """
    # Inlined integer (safe: int cast — no interpolation of user input).
    await session.execute(text(f"SET LOCAL hnsw.ef_search = {int(ef)}"))


__all__ = ["HNSW_EF_SEARCH", "set_hnsw_ef_search"]
