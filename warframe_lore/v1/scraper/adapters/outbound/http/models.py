"""HTTP response value object shared by outbound adapters."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class FetchResponse:
    url: str
    status: int
    content: bytes
    content_type: str
    headers: dict[str, str]
    encoding: str | None
    from_cache: bool = False
