"""HTTP output transport: Gzip + ETag/304 for the API and static files.

Single responsibility: write compressed responses (Gzip) with an ETag and
answer ``304 Not Modified`` when the client cache is up to date.  Routes
and payload assembly stay in :class:`warframe_lore.ui.handlers.ApiHandler`.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
from typing import Any


class HttpIOMixin:
    """Transport HTTP compressé (Gzip) avec cache ETag par fichier statique."""

    _static_cache: dict[tuple, tuple] = {}  # (root, filename) → (fp, gzip, etag)

    def _send_static(self, filename: str, content_type: str = "text/html") -> None:
        static_file = (self.root / filename) if self.root else Path(filename)
        if not static_file.is_file():
            self._send_json({"error": f"Static file '{filename}' not found"},
                            status=404)
            return
        try:
            st = static_file.stat()
        except OSError:
            self._send_json({"error": f"Static file '{filename}' unreadable"},
                            status=500)
            return
        fingerprint = (st.st_mtime_ns, st.st_size)
        key = (str(self.root), filename)
        cached = self._static_cache.get(key)
        if cached is None or cached[0] != fingerprint:
            compressed = gzip.compress(static_file.read_bytes())
            etag = '"' + hashlib.md5(
                f"{fingerprint[0]}:{fingerprint[1]}:{len(compressed)}"
                .encode("ascii")).hexdigest() + '"'
            cached = (fingerprint, compressed, etag)
            self._static_cache[key] = cached
        _, compressed, etag = cached
        if self.headers.get("If-None-Match") == etag:
            self._send_not_modified(etag)
            return
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Encoding", "gzip")
        self.send_header("Content-Length", str(len(compressed)))
        self.send_header("ETag", etag)
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(compressed)

    def _send_json(self, payload: Any, status: int = 200) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        compressed = gzip.compress(raw)
        etag = '"' + hashlib.md5(compressed).hexdigest() + '"'
        if self.headers.get("If-None-Match") == etag:
            self._send_not_modified(etag)
            return
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Encoding", "gzip")
        self.send_header("Content-Length", str(len(compressed)))
        self.send_header("ETag", etag)
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(compressed)

    def _send_not_modified(self, etag: str) -> None:
        """Réponse 304 pour un client dont le cache est à jour (ETag)."""
        self.send_response(304)
        self.send_header("ETag", etag)
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
