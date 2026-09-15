"""Orchestration: bounded-concurrency loop with automatic fallback.

Each URL is processed under an ``asyncio.Semaphore`` (3 by default). The
primary extractor (Wikitext API) is preferred; on failure the pipeline logs
the error and falls back to the Playwright DOM extractor before chunking.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence

from .chunking import chunk_into_lorechunks
from .extractors import BaseExtractor, ExtractedPage, MediaWikiExtractor
from .models import LoreChunk
from .resilience import DEFAULT_CONCURRENCY, ConcurrencyGuard

logger = logging.getLogger(__name__)

__all__ = ["ExtractionPipeline", "run_pipeline"]


class ExtractionPipeline:
    """Drives extraction + semantic chunking over a list of page URLs."""

    def __init__(
        self,
        primary: BaseExtractor | None = None,
        fallback: BaseExtractor | None = None,
        concurrency: int = DEFAULT_CONCURRENCY,
    ) -> None:
        self._primary = primary or MediaWikiExtractor()
        self._fallback = fallback
        self._guard = ConcurrencyGuard(limit=concurrency)

    async def process_page(self, url: str) -> list[LoreChunk]:
        """Extract ``url`` (with fallback) and slice it into chunks."""
        page = await self._guard.run(lambda: self._extract_with_fallback(url))
        chunks = chunk_into_lorechunks(
            text=page.text,
            source_url=page.source_url,
            page_title=page.page_title,
            metadata=page.metadata,
        )
        logger.info("Page '%s' -> %d chunks", page.page_title, len(chunks))
        return chunks

    async def run(self, urls: Sequence[str]) -> list[LoreChunk]:
        """Process all ``urls`` concurrently and flatten the chunks.

        Per-URL failures are caught and logged; only successful pages
        contribute chunks.
        """
        results = await asyncio.gather(
            *(self.process_page(url) for url in urls), return_exceptions=True
        )
        chunks: list[LoreChunk] = []
        for url, outcome in zip(urls, results, strict=True):
            if isinstance(outcome, Exception):
                logger.error("URL '%s' failed: %s", url, outcome)
                continue
            chunks.extend(outcome)
        return chunks

    async def _extract_with_fallback(self, url: str) -> ExtractedPage:
        """Primary extractor first; ``self._fallback`` on any failure."""
        logger.info("Extracting '%s' via %s", url, type(self._primary).__name__)
        try:
            page = await self._primary.extract(url)
            logger.info("Primary extraction OK for '%s'", url)
            return page
        except Exception as exc:  # noqa: BLE001 - fallback is the safety net
            logger.error(
                "Primary extractor failed for '%s' (%s); falling back...",
                url,
                exc,
            )
            if self._fallback is None:
                raise
            logger.info(
                "Extracting '%s' via %s",
                url,
                type(self._fallback).__name__,
            )
            return await self._fallback.extract(url)


async def run_pipeline(
    urls: Sequence[str],
    *,
    primary: BaseExtractor | None = None,
    fallback: BaseExtractor | None = None,
    concurrency: int = DEFAULT_CONCURRENCY,
) -> list[LoreChunk]:
    """Convenience wrapper: build a pipeline and run it."""
    pipeline = ExtractionPipeline(
        primary=primary, fallback=fallback, concurrency=concurrency
    )
    return await pipeline.run(urls)
