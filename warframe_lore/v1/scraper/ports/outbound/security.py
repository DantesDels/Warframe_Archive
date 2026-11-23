"""Outbound port for fetch-time security/policy."""

from __future__ import annotations

from typing import Protocol

from ...security.models import ScanResult


class SecurityPolicyPort(Protocol):
    """Outbound: authorize URLs/payloads before ingestion."""

    def check_url(self, url: str) -> ScanResult: ...
    def check_payload(self, url: str, content: bytes,
                      content_type: str) -> ScanResult: ...
