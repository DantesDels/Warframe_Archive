"""P1 cleaning/dedup/RAG contracts."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from warframe_lore.v1.scraper.UI.artifacts import chunk_text, emit_artifacts
from warframe_lore.v1.scraper.use_cases.pipeline.base import (
    PipelineContext,
    PipelineItem,
)
from warframe_lore.v1.scraper.use_cases.pipeline.stages_near_dedupe import (
    NearDedupeStage,
)
from warframe_lore.v1.scraper.use_cases.pipeline.stages_normalize import NormalizeStage


class _Page:
    def __init__(
        self, content: str, url: str = "https://ex/a", raw: bytes | None = None
    ):
        self.content = content
        self.url = url
        self.raw = raw
        self.content_type = "text/html"
        self.metadata: dict[str, str] = {}


class DedupeRagTests(unittest.TestCase):
    def test_normalize_detects_language_and_cleans(self):
        page = _Page("  Bonjour   le monde\n\nSubscribe now\nTexte utile  ")
        item = PipelineItem(page=page)
        out = NormalizeStage().run(
            [item], PipelineContext(source={}, universe_id="u")
        )
        self.assertTrue(out[0].accepted)
        self.assertNotIn("Subscribe", out[0].page.content)
        self.assertEqual(out[0].page.metadata.get("language"), "fr")

    def test_near_dedupe_rejects_similar(self):
        a = PipelineItem(page=_Page("alpha beta gamma delta epsilon zeta"))
        b = PipelineItem(page=_Page("alpha beta gamma delta epsilon zeta eta"))
        out = NearDedupeStage().run([a, b], PipelineContext(source={}, universe_id="u"))
        self.assertTrue(out[0].accepted)
        self.assertFalse(out[1].accepted)

    def test_chunk_and_vector_export(self):
        chunks = chunk_text("Titre\n\n" + ("para " * 300), max_chars=200, overlap=20)
        self.assertGreater(len(chunks), 1)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            manifest = emit_artifacts(
                out,
                {"id": "u", "name": "U"},
                [{
                    "id": "d1", "title": "t", "url": "u",
                    "content": "hello world", "excerpt": "e",
                }],
                ["json"],
                rag_coupling=True,
            )
            self.assertTrue((out / "chunks.jsonl").exists())
            self.assertTrue((out / "vectors.sqlite.json").exists())
            self.assertEqual(manifest["schema_version"], "1.1")
