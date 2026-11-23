"""Unified bounded multimodal processing (OCR, ASR, Vision)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..capabilities.models import MultimodalBudget, UniverseCapabilities
from ..ports.outbound.sources import CollectedPage
from .asr import AsrBackend, transcribe_media
from .guards import classify_media_kind, enforce_size_limit
from .ocr import OcrBackend, extract_ocr_text
from .vision import VisionBackend, analyze_visual


def process_multimodal_bytes(
    path: Path,
    raw: bytes,
    budget: MultimodalBudget | dict[str, Any],
    *,
    content_type: str = "",
    ocr_backend: OcrBackend | None = None,
    asr_backend: AsrBackend | None = None,
    vision_backend: VisionBackend | None = None,
    duration_override: float | None = None,
) -> CollectedPage:
    """Process one image, scanned PDF or audio/video file under strict limits."""
    cfg = _as_budget(budget)
    if not cfg.enabled:
        raise RuntimeError("Connecteur multimodal désactivé pour cet Univers.")
    enforce_size_limit(raw, cfg.max_file_mb)
    kind = classify_media_kind(path, content_type)
    ext = path.suffix.lower()

    if kind == "media":
        if not cfg.asr:
            raise RuntimeError("Transcription ASR désactivée dans les capacités.")
        text, engine, duration = transcribe_media(
            raw,
            ext=ext,
            max_media_minutes=cfg.max_media_minutes,
            duration_override=duration_override,
            backend=asr_backend,
        )
        return CollectedPage(
            title=path.name,
            url=str(path),
            content=text,
            raw=raw,
            content_type=content_type or "audio/media",
            metadata={
                "modality": "asr",
                "engine": engine,
                "duration_seconds": round(duration, 2),
            },
        )

    if kind == "pdf":
        if not cfg.ocr:
            raise RuntimeError("OCR PDF désactivé dans les capacités.")
        text, engine = extract_ocr_text(raw, ext=".pdf", backend=ocr_backend)
        return CollectedPage(
            title=path.name,
            url=str(path),
            content=text,
            raw=raw,
            content_type=content_type or "application/pdf",
            metadata={"modality": "ocr", "engine": engine},
        )

    if kind == "image":
        if not cfg.ocr and not cfg.vision:
            raise RuntimeError("OCR et Vision désactivés dans les capacités.")
        ocr_text, ocr_engine = ("", "disabled")
        if cfg.ocr:
            ocr_text, ocr_engine = extract_ocr_text(
                raw, ext=ext or ".png", backend=ocr_backend
            )
        if cfg.vision:
            markdown, vmeta = analyze_visual(
                raw, name=path.name, ocr_text=ocr_text, backend=vision_backend
            )
            return CollectedPage(
                title=path.name,
                url=str(path),
                content=markdown,
                raw=raw,
                content_type=content_type or "image/binary",
                metadata={
                    "modality": "vision",
                    "ocr_engine": ocr_engine,
                    "vision": vmeta,
                },
            )
        return CollectedPage(
            title=path.name,
            url=str(path),
            content=ocr_text,
            raw=raw,
            content_type=content_type or "image/binary",
            metadata={"modality": "ocr", "engine": ocr_engine},
        )

    raise ValueError(f"Format multimodal non pris en charge : {path.name}")


def _as_budget(budget: MultimodalBudget | dict[str, Any]) -> MultimodalBudget:
    if isinstance(budget, MultimodalBudget):
        return budget
    return UniverseCapabilities.from_dict({"multimodal": budget}).multimodal
