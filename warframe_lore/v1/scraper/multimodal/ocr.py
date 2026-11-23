"""Bounded OCR extractor for images and scanned PDFs with graceful fallback."""

from __future__ import annotations

import io
from collections.abc import Callable

OcrBackend = Callable[[bytes, str], str]


def extract_ocr_text(
    raw: bytes,
    *,
    ext: str = ".png",
    backend: OcrBackend | None = None,
) -> tuple[str, str]:
    """Extract text via OCR for images or scanned PDFs; returns (text, engine)."""
    if backend is not None:
        return str(backend(raw, ext) or "").strip(), "custom_ocr"
    if ext.lower() == ".pdf":
        return _extract_pdf_with_ocr_fallback(raw)
    return _ocr_image_bytes(raw)


def _extract_pdf_with_ocr_fallback(raw: bytes) -> tuple[str, str]:
    embedded = _extract_pdf_text_layer(raw)
    if len(embedded) >= 40:
        return embedded, "pypdf_text"
    ocr_parts = _ocr_pdf_embedded_images(raw)
    if ocr_parts:
        return "\n".join(ocr_parts).strip(), "pytesseract_pdf"
    return embedded, "ocr_unavailable"


def _extract_pdf_text_layer(raw: bytes) -> str:
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(io.BytesIO(raw))
        return "\n".join((p.extract_text() or "") for p in reader.pages).strip()
    except Exception:  # noqa: BLE001
        return ""


def _ocr_pdf_embedded_images(raw: bytes) -> list[str]:
    texts: list[str] = []
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(io.BytesIO(raw))
        for page in reader.pages[:25]:
            for img in getattr(page, "images", []):
                text, _eng = _ocr_image_bytes(bytes(img.data))
                if text:
                    texts.append(text)
    except Exception:  # noqa: BLE001
        return []
    return texts


def _ocr_image_bytes(raw: bytes) -> tuple[str, str]:
    try:
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore

        with Image.open(io.BytesIO(raw)) as img:
            text = str(pytesseract.image_to_string(img) or "").strip()
            return text, "pytesseract"
    except Exception:  # noqa: BLE001
        return "", "ocr_unavailable"
