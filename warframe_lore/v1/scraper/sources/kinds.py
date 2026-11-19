"""Enumeration of source kinds and lifecycle statuses."""

from __future__ import annotations

from enum import StrEnum


class SourceKind(StrEnum):
    """How a source must be fetched."""

    DOCUMENT = "document"
    WEBSITE = "website"
    API = "api"


class SourceStatus(StrEnum):
    """Where a source stands in the curation workflow."""

    CANDIDATE = "candidate"
    APPROVED = "approved"
    REJECTED = "rejected"
    DISABLED = "disabled"
