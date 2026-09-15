"""Data models of the decoupled RAG extraction pipeline.

``LoreChunk`` is the validated unit ingested by a vector database. It
carries the provenance of the extracted text (source page, URL) and a
free-form ``metadata`` dictionary for associated properties (infoboxes,
## categories, author, ...).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, HttpUrl, field_validator

MIN_CONTENT_LENGTH = 50

__all__ = ["LoreChunk", "MIN_CONTENT_LENGTH"]


class LoreChunk(BaseModel):
    """A semantic section of a wiki page, ready for vectorisation.

    Validation rules:
    - ``source_url`` must be a well-formed HTTP(S) URL;
    - ``content`` must hold at least ``MIN_CONTENT_LENGTH`` characters
      (after leading/trailing whitespace removal).
    """

    source_url: HttpUrl
    page_title: str = Field(..., min_length=1, description="Nom de la page wiki.")
    section_title: str = Field(..., min_length=1,
                               description="Titre de la section logique.")
    content: str = Field(
        ..., min_length=MIN_CONTENT_LENGTH, description="Text brut de la section."
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Propriétés associées (infoboxes, ...)."
    )

    @field_validator("content", "page_title", "section_title", mode="before")
    @classmethod
    def _strip_whitespace(cls, value: Any) -> Any:
        """Normalize text fields before length validation."""
        if isinstance(value, str):
            return value.strip()
        return value

    def to_payload(self) -> dict[str, Any]:
        """Serialisable representation (``source_url`` as plain string)."""
        return {
            "source_url": str(self.source_url),
            "page_title": self.page_title,
            "section_title": self.section_title,
            "content": self.content,
            "metadata": self.metadata,
        }
