"""Decoupled RAG extraction pipeline (Warframe Lore Wiki)."""

from .chunking import chunk_into_lorechunks, INTRODUCTION_TITLE
from .extractors import (
    BaseExtractor,
    ExtractedPage,
    MediaWikiExtractor,
    PlaywrightFallbackExtractor,
)
from .models import LoreChunk, MIN_CONTENT_LENGTH
from .pipeline import ExtractionPipeline, run_pipeline
from .resilience import DEFAULT_CONCURRENCY, MAX_ATTEMPTS

__all__ = [
    "BaseExtractor",
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