"""Domain security service for fetch-time URL/payload checks."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from urllib.parse import urlparse

from ..observability.network import resolve_host
from .models import ScanResult
from .scanner import scan_payload as scan_payload_content


@dataclass(slots=True)
class FetchPolicy:
    max_bytes: int = 5_000_000
    allowed_schemes: tuple[str, ...] = ("http", "https")
    quarantine_dir: str = ""


def check_url(url: str, policy: FetchPolicy | None = None) -> ScanResult:
    pol = policy or FetchPolicy()
    value = (url or "").strip()
    parsed = urlparse(value)
    if parsed.scheme not in pol.allowed_schemes:
        return ScanResult(False, "Schéma URL non autorisé.", "blocked_scheme", value)
    host = parsed.hostname or ""
    if not host:
        return ScanResult(False, "Hôte URL manquant.", "blocked_host", value)
    if _is_private_host(host):
        return ScanResult(False, "Hôte privé/boucle locale bloqué.",
                          "blocked_private_ip", value)
    return ScanResult(True, "URL autorisée.", "allowed_url", value)


def check_payload(url: str, content: bytes, content_type: str,
                  policy: FetchPolicy | None = None) -> ScanResult:
    pol = policy or FetchPolicy()
    if len(content) > pol.max_bytes:
        return ScanResult(False, "Taille de contenu au-delà du budget.",
                          "blocked_max_bytes", url)
    mime_ok = _mime_allowed(content_type)
    if mime_ok is False:
        return ScanResult(False, "Type MIME non autorisé.", "blocked_mime", url)
    return scan_payload_content(url, content=content, content_type=content_type)


def _mime_allowed(content_type: str) -> bool | None:
    ctype = (content_type or "").split(";")[0].strip().lower()
    if not ctype:
        return None
    blocked = {
        "application/x-msdownload", "application/x-executable",
        "application/x-sh", "application/java-archive",
    }
    if ctype in blocked:
        return False
    return True


def _is_private_host(host: str) -> bool:
    lowered = host.lower()
    if lowered == "localhost":
        return True
    try:
        infos = resolve_host(host)
    except Exception:
        return False
    for info in infos:
        ip = info[4][0]
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            continue
        private = addr.is_private or addr.is_loopback or addr.is_link_local
        if private or addr.is_reserved:
            return True
    return False
