"""Minimal network access for media resources."""

from __future__ import annotations

import urllib.request
from pathlib import Path


def http_get(url: str, timeout: int = 60) -> bytes:
    request = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def download_to(url: str, target: Path, timeout: int = 60) -> Path:
    payload = http_get(url, timeout=timeout)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return target
