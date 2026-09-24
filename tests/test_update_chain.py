"""Chain-wiring tests for ``cephalon update`` (``warframe_lore.update.run``).

Pure mock-based tests (no database, no network): they assert that the
single-command chain runs every phase — including the two RAG-embedding
ETLs (``ingest`` backfilling ``lore_chunks``, ``embed_structured``
rebuilding ``structured_chunks``) — against one shared database config.
"""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

# Make the patched attributes resolvable regardless of import order.
import warframe_lore.engram.scripts.embed_structured  # noqa: F401
import warframe_lore.engram.scripts.ingest  # noqa: F401
import warframe_lore.export  # noqa: F401
import warframe_lore.scraper  # noqa: F401
import warframe_lore.structured.pipeline  # noqa: F401
from warframe_lore.update.run import run_update

DB_URL = "postgresql+asyncpg://warframe:warframe@localhost:5432/warframe_lore"

_PATCH_TARGETS = (
    "warframe_lore.scraper.Scraper",
    "warframe_lore.structured.pipeline.run",
    "warframe_lore.export.PublicExportClient",
    "warframe_lore.db.manager.SQLDatabaseManager",
    "warframe_lore.update.lists.regenerate_story_eras",
    "warframe_lore.engram.scripts.ingest.run",
    "warframe_lore.engram.scripts.embed_structured.run",
)

_ETL_PATCH = "warframe_lore.structured.pipeline.run"
_INGEST_PATCH = "warframe_lore.engram.scripts.ingest.run"
_EMBED_PATCH = "warframe_lore.engram.scripts.embed_structured.run"


class UpdateChainRagTests(unittest.TestCase):
    """``cephalon update`` completes the RAG corpora with fresh vectors."""

    def setUp(self) -> None:
        self._mocks: dict[str, object] = {}
        for path in _PATCH_TARGETS:
            mocker = patch(path, autospec=True)
            self._mocks[path] = mocker.start()
            self.addCleanup(mocker.stop)
        # Deterministic returns: AsyncMock's default return_value is itself an
        # AsyncMock (a `dict(counts)` or a numeric check would misbehave).
        self._mock(_ETL_PATCH).return_value = {}
        self._mock(_INGEST_PATCH).return_value = 7
        self._mock(_EMBED_PATCH).return_value = 12
        self._mock("warframe_lore.update.lists.regenerate_story_eras").return_value = {}

    def _mock(self, path: str):
        return self._mocks[path]

    def test_chain_wires_both_rag_embedding_etls(self):
        results = asyncio.run(run_update(DB_URL))

        self.assertIn("lore_chunks", results)
        self.assertIn("structured_chunks", results)
        self.assertEqual(results["lore_chunks"], 7)
        self.assertEqual(results["structured_chunks"], 12)

    def test_chain_embeds_pending_lore_and_rebuilds_structured(self):
        asyncio.run(run_update(DB_URL))

        self.assertTrue(self._mock(_INGEST_PATCH).called)
        self.assertTrue(self._mock(_EMBED_PATCH).called)

    def test_chain_shares_one_config_across_etl_and_embeddings(self):
        asyncio.run(run_update(DB_URL))

        etl_config = self._mock(_ETL_PATCH).call_args.args[0]
        ingest_config = self._mock(_INGEST_PATCH).call_args.args[0]
        embed_config = self._mock(_EMBED_PATCH).call_args.args[0]
        self.assertIs(etl_config, ingest_config)
        self.assertIs(ingest_config, embed_config)
        self.assertEqual(etl_config.database_url, DB_URL)


if __name__ == "__main__":
    unittest.main()
