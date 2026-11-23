"""LZMA connector."""

from __future__ import annotations

import lzma
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ....collect.http import browser_headers
from ....ports.outbound.sources import CollectedPage, ConnectorContext


class LzmaConnector:
    name = "lzma"
    kinds = ("website", "api", "document")

    def can_handle(self, source: dict[str, Any], _ctx: ConnectorContext) -> bool:
        return str(source.get("location", "")).lower().endswith(".lzma")

    def collect(
        self, source: dict[str, Any], ctx: ConnectorContext
    ) -> list[CollectedPage]:
        url = str(source.get("location", "")).strip()
        use_cache = bool(ctx.limits.get("use_cache", True))
        resp = ctx.client.get(url, headers=browser_headers(), use_cache=use_cache)
        text = _decode_lzma(resp.content)
        parsed_url = urlparse(str(resp.url))
        title = Path(parsed_url.path).name or parsed_url.netloc
        return [CollectedPage(title=title, url=resp.url, content=text,
                              from_cache=resp.from_cache, raw=resp.content,
                              content_type=str(resp.content_type))]


def _decode_lzma(data: bytes) -> str:
    try:
        return lzma.decompress(data).decode("utf-8", errors="replace")
    except lzma.LZMAError:
        dec = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE)
        out = bytearray()
        for i in range(0, len(data), 64):
            try:
                out.extend(dec.decompress(data[i:i + 64], max_length=1 << 20))
            except lzma.LZMAError:
                break
            if dec.eof:
                break
        if not out:
            raise
        return out.decode("utf-8", errors="replace")
