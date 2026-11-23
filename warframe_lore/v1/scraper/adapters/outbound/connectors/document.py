"""Local document connector."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ....collect.binary_text import decode_lzma
from ....ports.outbound.sources import CollectedPage, ConnectorContext


def _extract_text(path: Path, raw: bytes) -> str:
    suffix = path.suffix.lower()
    if suffix == '.lzma':
        return decode_lzma(raw)
    if suffix in {'.txt', '.md', '.markdown', '.json', '.xml', '.html', '.htm', '.csv'}:
        return raw.decode('utf-8', errors='replace')
    if suffix == '.pdf':
        try:
            import io

            from pypdf import PdfReader  # type: ignore
            reader = PdfReader(io.BytesIO(raw))
            return "\n".join((page.extract_text() or '') for page in reader.pages)
        except Exception:
            return raw.decode('utf-8', errors='replace')
    if suffix == '.docx':
        try:
            import io

            import docx  # type: ignore
            doc = docx.Document(io.BytesIO(raw))
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception:
            return raw.decode('utf-8', errors='replace')
    if suffix == '.pptx':
        try:
            import io

            from pptx import Presentation  # type: ignore
            pres = Presentation(io.BytesIO(raw))
            parts: list[str] = []
            for slide in pres.slides:
                for shape in slide.shapes:
                    txt = getattr(shape, 'text', '')
                    if txt:
                        parts.append(str(txt))
            return "\n".join(parts)
        except Exception:
            return raw.decode('utf-8', errors='replace')
    return raw.decode('utf-8', errors='replace')


class DocumentConnector:
    name = "document"
    kinds = ("document",)

    def can_handle(self, source: dict[str, Any], _ctx: ConnectorContext) -> bool:
        loc = str(source.get("location", "")).strip()
        return source.get("kind") == "document" or Path(loc).exists()

    def collect(
        self, source: dict[str, Any], _ctx: ConnectorContext
    ) -> list[CollectedPage]:
        path = Path(str(source.get("location", "")).strip())
        raw = path.read_bytes()
        text = _extract_text(path, raw)
        return [CollectedPage(title=path.name, url=str(path), content=text, raw=raw)]
