"""Outbound adapter shim: fetch-time policy delegated to domain service."""

from __future__ import annotations

from ....security.fetch_policy import FetchPolicy, check_payload, check_url

__all__ = ["FetchPolicy", "check_payload", "check_url"]
