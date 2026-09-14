"""ApiHandler — HTTP dispatcher for the local UI (routes + static files).

Single responsibility: dispatch one GET request to the right layer — fixed static
assets and the two Vue SPAs (:mod:`static_pages`), the ``/api/*`` endpoints
(:mod:`api_routes`), the cached wiki images (:mod:`media`) — and turn any
unexpected error into a generic 500.  Payload assembly lives in :mod:`payloads`,
the Gzip/ETag transport in :mod:`httpio`.
"""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, unquote

from ...media import MediaIndex
from ..data.store import LoreStore
from .api_routes import API_ROUTES
from .httpio import HttpIOMixin
from .media import IMMUTABLE_CACHE, media_image
from .static_pages import spa_route, static_route


class ApiHandler(HttpIOMixin, BaseHTTPRequestHandler):
    """Routes ``/api/*`` and the static files (store and media injected)."""

    server_version = "CephalonUI/1.0"
    store: LoreStore = None  # injecté par la fabrique (ui.server)
    media: MediaIndex = None  # injecté par la fabrique
    root: Path = None        # répertoire des fichiers statiques

    def log_message(self, format, *args):  # noqa: A002  (stdlib signature)
        return  # silent; logs go through the launcher.

    def do_GET(self) -> None:
        """Serve one GET request; any error answers a generic 500."""
        path, _, query_raw = self.path.partition("?")
        query = parse_qs(query_raw)
        if path.startswith("/api/"):
            # Megafiles are re-read on change (fingerprint), per API call.
            self.store.maybe_reload()
        try:
            self._route(path, query)
        except Exception as exc:  # noqa: BLE001  (réponse 500 générique)
            self._server_error(exc)

    def _route(self, path: str, query: dict) -> None:
        """Static assets, then SPAs, then images, then the API table."""
        asset = static_route(path)
        if asset is not None:
            self._send_static(*asset)
            return
        page = spa_route(path)
        if page is not None:
            self._send_static(*page)
            return
        if path.startswith("/media/"):
            self._send_media(unquote(path.rsplit("/", 1)[-1]))
            return
        endpoint = API_ROUTES.get(path)
        if endpoint is not None:
            endpoint(self, query)
            return
        self._send_json({"error": "Not found"}, status=404)

    def _send_media(self, filename: str) -> None:
        """One cached wiki image, with an immutable cache header."""
        payload, content_type, error = media_image(self.media, filename)
        if payload is None:
            self._send_json(error, status=404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", IMMUTABLE_CACHE)
        self.end_headers()
        self.wfile.write(payload)

    def _server_error(self, exc: Exception) -> None:
        """Generic 500 (the connection may already be broken: stay silent)."""
        try:
            self._send_json({"error": str(exc)}, status=500)
        except OSError:
            pass


__all__ = ["ApiHandler"]
