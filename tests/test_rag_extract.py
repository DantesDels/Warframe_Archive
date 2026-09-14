"""Decoupled RAG extraction pipeline: models, chunking, resilience, strategy.

Covers the Pydantic ``LoreChunk`` contract, the semantic H2/H3 splitting,
the Tenacity + semaphore mechanics and the primary/fallback orchestration
with fake extractors (no network access).
"""

from __future__ import annotations

import asyncio
import unittest

import aiohttp
from pydantic import ValidationError

from warframe_lore.rag_extract import (
    BaseExtractor,
    ExtractedPage,
    ExtractionPipeline,
    LoreChunk,
    MediaWikiExtractor,
    chunk_into_lorechunks,
)
from warframe_lore.rag_extract.chunking import INTRODUCTION_TITLE
from warframe_lore.rag_extract.extractors import (
    _infobox_metadata,
    _title_from_url,
    _wikitext_to_markdown,
)
from warframe_lore.rag_extract.resilience import (
    DEFAULT_CONCURRENCY,
    MAX_ATTEMPTS,
    retry_network,
)

URL = "https://warframe.fandom.com/wiki/Ordis"


class LoreChunkTests(unittest.TestCase):
    def test_valid_chunk_passes(self) -> None:
        chunk = LoreChunk(
            source_url=URL,
            page_title="Ordis",
            section_title="Identité",
            content="Avant de devenir un Cephalon, Ordis était un mercenaire.",
            metadata={"Nom": "Ordan Karris"},
        )
        self.assertEqual(chunk.page_title, "Ordis")
        self.assertEqual(chunk.metadata["Nom"], "Ordan Karris")
        payload = chunk.to_payload()
        self.assertEqual(payload["source_url"], URL)

    def test_content_too_short_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            LoreChunk(
                source_url=URL,
                page_title="Ordis",
                section_title="Identité",
                content="trop court",
            )

    def test_invalid_url_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            LoreChunk(
                source_url="not-a-url",
                page_title="Ordis",
                section_title="Identité",
                content="x" * 60,
            )

    def test_content_stripped_before_min_length(self) -> None:
        with self.assertRaises(ValidationError):
            LoreChunk(
                source_url=URL,
                page_title="Ordis",
                section_title="Identité",
                content="   " + "x" * 48 + "\n\n",
            )


class ChunkingTests(unittest.TestCase):
    TEXT = (
        "Ce paragraphe d'introduction est volontairement assez long pour "
        "dépasser le seuil minimal de cinquante caractères exigé.\n\n"
        "## Identité passée\n\n"
        "Avant de devenir un Cephalon, Ordis était un mercenaire nommé "
        "Ordan Karris qui servait les Orokin.\n\n"
        "### Enfance\n\n"
        "Les détails de son enfance restent flous dans les archives.\n\n"
        "## Fin\n"
    )

    def test_lead_becomes_introduction(self) -> None:
        chunks = chunk_into_lorechunks(
            self.TEXT, source_url=URL, page_title="Ordis"
        )
        self.assertEqual(chunks[0].section_title, INTRODUCTION_TITLE)
        self.assertIn("d'introduction", chunks[0].content)

    def test_h2_h3_split_and_metadata(self) -> None:
        chunks = chunk_into_lorechunks(
            self.TEXT,
            source_url=URL,
            page_title="Ordis",
            metadata={"Clan": "Orokin"},
        )
        self.assertEqual(len(chunks), 3)
        self.assertEqual(chunks[1].section_title, "Identité passée")
        self.assertEqual(chunks[2].section_title, "Enfance")
        for chunk in chunks:
            self.assertEqual(chunk.metadata["Clan"], "Orokin")
            self.assertEqual(str(chunk.source_url), URL)

    def test_all_chunks_respect_min_length(self) -> None:
        chunks = chunk_into_lorechunks(
            self.TEXT, source_url=URL, page_title="Ordis"
        )
        self.assertTrue(chunks)
        for chunk in chunks:
            self.assertGreaterEqual(len(chunk.content), 50)

    def test_no_headings_single_chunk(self) -> None:
        long = "Tout le texte d'une page sans aucun titre structuré. " * 8
        chunks = chunk_into_lorechunks(long, source_url=URL, page_title="PageX")
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].section_title, INTRODUCTION_TITLE)

    def test_undersized_trailing_block_merged(self) -> None:
        paragraph = "Paragraphe du bloc A assez long pour être retenu. " * 4
        text = "## Section A\n\n" + paragraph
        text += "\n## Section B\n\nCourt."
        chunks = chunk_into_lorechunks(text, source_url=URL, page_title="PageX")
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].section_title, "Section A")
        self.assertIn("Court.", chunks[0].content)


class WikitextCleaningTests(unittest.TestCase):
    def test_mediawiki_title_from_url(self) -> None:
        self.assertEqual(
            _title_from_url("https://warframe.fandom.com/wiki/Ordis_Karris"),
            "Ordis Karris",
        )

    def test_headings_kept_as_markdown(self) -> None:
        cleaned = _wikitext_to_markdown(
            "== Identité ==\n\nTexte blabla ici.\n\n=== Enfance ===\n\nEncore du texte."
        )
        self.assertIn("## Identité", cleaned)
        self.assertIn("### Enfance", cleaned)

    def test_templates_and_links_cleaned(self) -> None:
        cleaned = _wikitext_to_markdown(
            "[[Ordis|Le Cephalon]] servait {{Agresseur}} durant la guerre."
        )
        self.assertIn("Le Cephalon servait", cleaned)
        self.assertNotIn("Agresseur", cleaned)

    def test_infobox_extracted(self) -> None:
        meta = _infobox_metadata(
            "{{Infobox_Warframe|nom=Excalibur|classe=Polyvalent|axiomes=2}}"
        )
        self.assertEqual(meta["nom"], "Excalibur")
        self.assertEqual(meta["classe"], "Polyvalent")


class ResilienceTests(unittest.TestCase):
    def test_constants(self) -> None:
        self.assertEqual(MAX_ATTEMPTS, 3)
        self.assertEqual(DEFAULT_CONCURRENCY, 3)

    def test_retry_network_recovers(self) -> None:
        calls = {"n": 0}

        @retry_network(attempts=3)
        async def flaky() -> int:
            calls["n"] += 1
            if calls["n"] == 1:
                raise aiohttp.ClientConnectionError("boom")
            return 42

        self.assertEqual(asyncio.run(flaky()), 42)
        self.assertEqual(calls["n"], 2)


class _FakeExtractor(BaseExtractor):
    def __init__(self, page: ExtractedPage, fail: bool = False,
                 delay: float = 0.02) -> None:
        self.page = page
        self.fail = fail
        self.delay = delay
        self.calls = 0
        self._active = 0
        self.max_active = 0

    async def extract(self, url: str) -> ExtractedPage:
        self.calls += 1
        self._active += 1
        self.max_active = max(self.max_active, self._active)
        await asyncio.sleep(self.delay)
        self._active -= 1
        if self.fail:
            raise RuntimeError("primary extractor failed")
        return self.page


class PipelineTests(unittest.TestCase):
    PAGE = ExtractedPage(
        source_url=URL,
        page_title="Ordis",
        text="## Histoire\n\n" + "Longue histoire de l'ancien mercenaire. " * 4,
        metadata={"Nom": "Ordan"},
    )

    def test_primary_extractor_used(self) -> None:
        extractor = _FakeExtractor(self.PAGE, fail=False)
        chunks = asyncio.run(ExtractionPipeline(primary=extractor).run([URL]))
        self.assertEqual(extractor.calls, 1)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].section_title, "Histoire")
        self.assertEqual(chunks[0].metadata["Nom"], "Ordan")
        self.assertEqual(str(chunks[0].source_url), URL)

    def test_fallback_on_primary_failure(self) -> None:
        primary = _FakeExtractor(self.PAGE, fail=True)
        fallback = _FakeExtractor(self.PAGE, fail=False)
        pipeline = ExtractionPipeline(primary=primary, fallback=fallback)
        chunks = asyncio.run(pipeline.run([URL]))
        self.assertEqual(primary.calls, 1)
        self.assertEqual(fallback.calls, 1)
        self.assertEqual(len(chunks), 1)

    def test_primary_failure_without_fallback_returns_empty(self) -> None:
        primary = _FakeExtractor(self.PAGE, fail=True)
        pipeline = ExtractionPipeline(primary=primary, fallback=None)
        chunks = asyncio.run(pipeline.run([URL]))
        self.assertEqual(primary.calls, 1)
        self.assertEqual(chunks, [])

    def test_concurrency_capped_at_three(self) -> None:
        primary = _FakeExtractor(self.PAGE, delay=0.05)
        pipeline = ExtractionPipeline(primary=primary, concurrency=3)
        chunks = asyncio.run(pipeline.run([URL] * 8))
        self.assertEqual(primary.calls, 8)
        self.assertLessEqual(primary.max_active, 3)
        self.assertEqual(len(chunks), 8)


class MediaWikiExtractorContractTests(unittest.TestCase):
    def test_extract_is_retriable_async(self) -> None:
        self.assertTrue(hasattr(MediaWikiExtractor.extract, "retry"))
        self.assertTrue(asyncio.iscoroutinefunction(MediaWikiExtractor.extract))


if __name__ == "__main__":
    unittest.main()
