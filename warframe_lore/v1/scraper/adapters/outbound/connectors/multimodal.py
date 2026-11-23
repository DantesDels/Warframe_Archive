"""Outbound connector delegating bounded image/PDF/audio/video to multimodal."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ....capabilities.models import MultimodalBudget, UniverseCapabilities
from ....multimodal.guards import classify_media_kind
from ....multimodal.processor import process_multimodal_bytes
from ....ports.outbound.sources import CollectedPage, ConnectorContext


class MultimodalConnector:
    """Opt-in connector for OCR (images/scanned PDF), ASR (audio/video) & Vision."""

    name = "multimodal"
    kinds = ("media", "image", "audio", "video", "document")

    def can_handle(self, source: dict[str, Any], ctx: ConnectorContext) -> bool:
        cfg = _multimodal_budget(ctx)
        if not cfg.enabled:
            return False
        loc = str(source.get("location", "")).strip()
        if not loc:
            return False
        path = Path(loc)
        kind = classify_media_kind(path)
        if kind == "image":
            return cfg.ocr or cfg.vision
        if kind == "media":
            return cfg.asr
        if kind == "pdf":
            return cfg.ocr and path.is_file()
        return False

    def collect(
        self, source: dict[str, Any], ctx: ConnectorContext
    ) -> list[CollectedPage]:
        cfg = _multimodal_budget(ctx)
        loc = str(source.get("location", "")).strip()
        path = Path(loc)
        if path.is_file():
            raw = path.read_bytes()
            ctype = ""
        else:
            resp = ctx.client.get(loc, use_cache=True)
            raw = bytes(getattr(resp, "content", b""))
            ctype = str(getattr(resp, "content_type", "") or "")
        page = process_multimodal_bytes(
            path,
            raw,
            cfg,
            content_type=ctype,
            ocr_backend=ctx.limits.get("ocr_backend"),
            asr_backend=ctx.limits.get("asr_backend"),
            vision_backend=ctx.limits.get("vision_backend"),
        )
        return [page]


def _multimodal_budget(ctx: ConnectorContext) -> MultimodalBudget:
    raw = ctx.limits.get("multimodal")
    if isinstance(raw, MultimodalBudget):
        return raw
    if isinstance(raw, dict):
        return UniverseCapabilities.from_dict({"multimodal": raw}).multimodal
    return MultimodalBudget(enabled=False)
