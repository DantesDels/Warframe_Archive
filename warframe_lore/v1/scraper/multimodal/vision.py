"""Bounded Vision analyzer for maps, diagrams and infographics."""

from __future__ import annotations

import struct
from collections.abc import Callable
from typing import Any

VisionBackend = Callable[[bytes, str], str]


def probe_image_metadata(raw: bytes) -> dict[str, Any]:
    """Extract image format, dimensions and visual layout hint from headers."""
    if raw[:8] == b"\x89PNG\r\n\x1a\n" and len(raw) >= 24:
        w, h = struct.unpack(">II", raw[16:24])
        return _format_meta("PNG", w, h)
    if raw[:2] == b"BM" and len(raw) >= 26:
        w, h = struct.unpack("<ii", raw[18:26])
        return _format_meta("BMP", abs(w), abs(h))
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return _pil_or_unknown(raw, "WEBP")
    if raw[:2] == b"\xff\xd8":
        return _pil_or_unknown(raw, "JPEG")
    return _pil_or_unknown(raw, "UNKNOWN")


def analyze_visual(
    raw: bytes,
    *,
    name: str = "",
    ocr_text: str = "",
    backend: VisionBackend | None = None,
) -> tuple[str, dict[str, Any]]:
    """Build structured Markdown description for a map, diagram or infographic."""
    meta = probe_image_metadata(raw)
    caption = ""
    engine = "metadata_vision"
    if backend is not None:
        caption = str(backend(raw, name) or "").strip()
        engine = "custom_vision"

    lines = [f"# {name or 'Visuel'}", ""]
    dims = (
        f"{meta['width']}x{meta['height']}"
        if meta["width"] and meta["height"]
        else "dimensions inconnues"
    )
    lines.append(
        f"- Format : {meta['format']} ({dims}) · Type visuel : {meta['layout_hint']}"
    )
    if caption:
        lines.extend(["", "## Description visuelle", caption])
    if ocr_text.strip():
        lines.extend(["", "## Texte extrait (OCR)", ocr_text.strip()])
    meta["engine"] = engine
    meta["has_caption"] = bool(caption)
    return "\n".join(lines).strip(), meta


def _format_meta(fmt: str, width: int, height: int) -> dict[str, Any]:
    ratio = width / float(height) if height > 0 else 1.0
    if ratio >= 1.6:
        hint = "carte / bannière"
    elif ratio <= 0.7:
        hint = "infographie verticale"
    else:
        hint = "schéma / illustration"
    return {"format": fmt, "width": width, "height": height, "layout_hint": hint}


def _pil_or_unknown(raw: bytes, fallback_fmt: str) -> dict[str, Any]:
    try:
        import io

        from PIL import Image  # type: ignore

        with Image.open(io.BytesIO(raw)) as img:
            w, h = img.size
            return _format_meta(str(img.format or fallback_fmt), w, h)
    except Exception:  # noqa: BLE001
        return {
            "format": fallback_fmt, "width": 0, "height": 0, "layout_hint": "visuel"
        }
