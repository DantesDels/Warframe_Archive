"""Decoupled RAG extraction pipeline (Warframe Lore Wiki)."""

from .chunking import INTRODUCTION_TITLE, chunk_into_lorechunks
from .dom_scraper import PlaywrightFallbackExtractor
from .extractors import (
    BaseExtractor,
    ExtractedPage,
    MediaWikiExtractor,
)
from .models import MIN_CONTENT_LENGTH, LoreChunk
from .pipeline import ExtractionPipeline, run_pipeline
from .resilience import DEFAULT_CONCURRENCY, MAX_ATTEMPTS

__all__ = [
    "BaseExtractor",
    "DEFAULT_CONCURRENCY",
    "ExtractedPage",
    "ExtractionPipeline",
    "INTRODUCTION_TITLE",
    "LoreChunk",
    "MAX_ATTEMPTS",
    "MIN_CONTENT_LENGTH",
    "MediaWikiExtractor",
    "PlaywrightFallbackExtractor",
    "chunk_into_lorechunks",
    "run_pipeline",
]
