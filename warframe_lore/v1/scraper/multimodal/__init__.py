"""Public API for Phase P5 bounded multimodal connectors."""

from __future__ import annotations

from .asr import AsrBackend, transcribe_media
from .guards import (
    ALL_MULTIMODAL_EXTS,
    IMAGE_EXTS,
    MEDIA_EXTS,
    PDF_EXTS,
    classify_media_kind,
    enforce_duration_limit,
    enforce_size_limit,
    probe_media_duration_seconds,
)
from .ocr import OcrBackend, extract_ocr_text
from .processor import process_multimodal_bytes
from .vision import VisionBackend, analyze_visual, probe_image_metadata

__all__ = [
    "ALL_MULTIMODAL_EXTS",
    "IMAGE_EXTS",
    "MEDIA_EXTS",
    "PDF_EXTS",
    "AsrBackend",
    "OcrBackend",
    "VisionBackend",
    "analyze_visual",
    "classify_media_kind",
    "enforce_duration_limit",
    "enforce_size_limit",
    "extract_ocr_text",
    "probe_image_metadata",
    "probe_media_duration_seconds",
    "process_multimodal_bytes",
    "transcribe_media",
]
