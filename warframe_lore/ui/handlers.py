"""ApiHandler — HTTP ``/api/*`` routes and static files (Gzip).

Single responsibility: route frontend requests to the data layer
(``LoreStore``), the media layer (``MediaIndex``) and static files.  The
Gzip/ETag transport lives in :mod:`warframe_lore.ui.httpio`.
"""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, unquote

from ..cleaner.formatting import cut_footer_noise, normalise_deep_headings
from ..media import MediaIndex
from ..timeline import children_payload, roots_payload
from .httpio import HttpIOMixin
from .patch_notes import _PATCH_HISTORY_HEADING, extract_patch_notes
from .store import LoreStore


class ApiHandler(HttpIOMixin, BaseHTTPRequestHandler):
    server_version = "CephalonUI/1.0"
    store: LoreStore = None  # injecté par la fabrique
    media: MediaIndex = None  # injecté par la fabrique
    root: Path = None        # répertoire des fichiers statiques

    # ------------------------------------------------------------ verbosity
    def log_message(self, format, *args):  # noqa: A002  (stdlib signature)
        return  # silent; logs go through the launcher.

    # ---------------------------------------------------------------- routes
    def do_GET(self) -> None:
        path, _, query_raw = self.path.partition("?")
        query = parse_qs(query_raw)
        if path.startswith("/api/"):
            self.store.maybe_reload()
        try:
            if path in ("/", "/index.html"):
                self._send_static("index.html")
            elif path == "/app.js":
                self._send_static("app.js", content_type="text/javascript")
            elif path == "/styles.css":
                self._send_static("styles.css", content_type="text/css")
            elif path == "/vendor/vue-flow.bundle.js":
                self._send_static("vendor/vue-flow.bundle.js",
                                  content_type="text/javascript")
            elif path == "/vendor/vue-flow.bundle.css":
                self._send_static("vendor/vue-flow.bundle.css",
                                  content_type="text/css")
            elif path == "/inspector/" or path.startswith("/inspector/"):
                self._send_inspector(path)
            elif path == "/timeline/" or path.startswith("/timeline/"):
                self._send_timeline(path)
            elif path == "/api/timeline/roots":
                self._send_json(roots_payload())
            elif path == "/api/timeline":
                parent_id = (query.get("parent_id") or [None])[0]
                if not parent_id:
                    self._send_json({"error": "parent_id manquant"},
                                    status=400)
                    return
                payload = children_payload(parent_id)
                if payload is None:
                    self._send_json({"error": "Noeud inconnu"}, status=404)
                    return
                self._send_json(payload)
            elif path == "/api/stats":
                self._send_json(self.store.stats())
            elif path == "/api/buckets":
                self._send_json(self.store.list_buckets())
            elif path == "/api/pages":
                self._send_json(self._pages_for_query(query))
            elif path == "/api/page":
                self._send_json(self._page_for_query(query))
            elif path == "/api/kim":
                self._send_json(self._kim_for_query(query))
            elif path == "/api/graph":
                title = unquote((query.get("title") or [""])[0])
                conv = unquote((query.get("conv") or [""])[0])
                self._send_json(self.store.kim_graph(title, conv) or {})
            elif path == "/api/recent":
                limit = int_from_query(query, "limit", 20)
                self._send_json(self.store.recent(limit=limit))
            elif path == "/api/search":
                q = (query.get("q") or [""])[0]
                limit = int_from_query(query, "limit", 50)
                bucket = (query.get("bucket") or [""])[0] or None
                canon = (query.get("canon") or [""])[0] or None
                self._send_json(self.store.search(
                    q, limit=limit, bucket=bucket, canon=canon))
            elif path == "/api/suggest":
                q = (query.get("q") or [""])[0]
                limit = int_from_query(query, "limit", 8)
                self._send_json(self.store.suggest(q, limit=limit))
            elif path == "/api/media":
                self._send_json(self._media_payload())
            elif path.startswith("/media/"):
                self._send_media(unquote(path.rsplit("/", 1)[-1]))
            else:
                self._send_json({"error": "Not found"}, status=404)
        except Exception as exc:  # noqa: BLE001  (réponse 500 générique)
            try:
                self._send_json({"error": str(exc)}, status=500)
            except OSError:
                pass

    # -------------------------------------------------------------- helpers
    def _send_inspector(self, path: str) -> None:
        """RAG Inspector (build Vue, page autonome ``/inspector/``).

        ``/inspector/`` sert ``index.html`` ; les assets hachés sont servis
        sous ``/inspector/assets/*`` depuis le dossier ``static/inspector``.
        """
        relative = path[len("/inspector/"):]
        if not relative:
            relative = "index.html"
        content_type = "text/html"
        if relative.endswith(".js"):
            content_type = "text/javascript"
        elif relative.endswith(".css"):
            content_type = "text/css"
        self._send_static(f"inspector/{relative}", content_type=content_type)

    def _send_timeline(self, path: str) -> None:
        """Timeline (build Vue, page autonome ``/timeline/``).

        ``/timeline/`` sert ``index.html`` ; les assets hachés sont servis
        sous ``/timeline/assets/*`` depuis le dossier ``static/timeline``.
        """
        relative = path[len("/timeline/"):]
        if not relative:
            relative = "index.html"
        content_type = "text/html"
        if relative.endswith(".js"):
            content_type = "text/javascript"
        elif relative.endswith(".css"):
            content_type = "text/css"
        self._send_static(f"timeline/{relative}", content_type=content_type)

    def _pages_for_query(self, query) -> list[dict]:
        bucket = (query.get("bucket") or [""])[0]
        if not bucket or not self.store.bucket_exists(bucket):
            return []
        return self.store.list_pages(bucket)

    def _page_for_query(self, query) -> dict | None:
        bucket = (query.get("bucket") or [""])[0]
        title = unquote((query.get("title") or [""])[0])
        if bucket and not self.store.bucket_exists(bucket):
            return None
        if self.store.bucket_exists(bucket):
            page = self.store.get_page(bucket, title)
        else:
            page = self.store.get_dialogue_page(title)
        if page is None:
            return None
        result = dict(page)
        content = result.get("content_markdown", "")
        # Relais du filtre footer du scraper : les megafiles servis n'ont pas
        # été regénérés depuis l'ajout de ``cut_footer_noise`` — on applique la
        # même troncature à la volée (navboxes/catégories/historique ``Update``)
        # AVANT l'extraction des patch notes, pour ne pas créer de versions
        # fantômes à partir des lignes de footer (``Update 37``, ``Hildryn``…).
        content = cut_footer_noise(normalise_deep_headings(content))
        if _PATCH_HISTORY_HEADING.search(content):
            patches, rest = extract_patch_notes(content)
            result["patch_notes"] = patches
            result["content_markdown"] = rest
        else:
            result["content_markdown"] = content
        return result

    def _kim_for_query(self, query) -> list[dict] | dict:
        title = unquote((query.get("title") or [""])[0])
        conv = unquote((query.get("conv") or [""])[0])
        mode = (query.get("mode") or [""])[0]
        if not title:
            return self.store.kim_pages()
        page = self.store.get_dialogue_page(title)
        content = (page or {}).get("content_markdown", "")
        if not page or not self.store._looks_like_dialogue(content):
            return {"character": None, "spoiler": None, "conversations": []}
        if not conv:
            conversations = self.store.kim_conversations(title)
            return {
                "character": title.rsplit("/", 1)[-1],
                "spoiler": self.store.spoiler_warning(content),
                "conversations": [
                    {"id": c["id"], "title": c["title"],
                     "rank": c["rank"], "source": c.get("source", "wiki")}
                    for c in conversations
                ],
            }
        for conversation in self.store.kim_conversations(title):
            if conversation["id"] != conv:
                continue
            result = {
                "id": conversation["id"],
                "title": conversation["title"],
                "rank": conversation["rank"],
            }
            character = title.rsplit("/", 1)[-1].strip()
            dm_detail = self.store.kim_dm.conversation(character, conv)
            if mode == "sim":
                if dm_detail is not None:
                    result["script"] = dm_detail["script"]
                else:
                    result["script"] = self.store._build_kim_script(
                        conversation["body"])
                result["spoiler"] = self.store.spoiler_warning(content)
            else:
                if dm_detail is not None:
                    result["messages"] = dm_detail["messages"]
                else:
                    result["messages"] = self.store._parse_dialogue(
                        conversation["body"])
                result["source"] = dm_detail["source"] if dm_detail else "wiki"
            return result
        return {"id": None, "title": None, "rank": None, "messages": []}

    # ---------------------------------------------------------------- média
    def _media_payload(self) -> dict:
        media = self.media
        if media is None:
            return {"available": False, "count": 0,
                    "titles": {}, "speakers": {}, "buckets": {}}
        media.ensure()
        if not media.available():
            return {"available": False, "count": 0,
                    "titles": {}, "speakers": {}, "buckets": {}}
        return media.media_payload(
            page_titles_by_bucket=self.store.page_titles_by_bucket(),
            speakers=self.store.kim_speakers(),
        )

    def _send_media(self, filename: str) -> None:
        media = self.media
        if media is None or not filename:
            self._send_json({"error": "Not found"}, status=404)
            return
        media.ensure()
        if not media.available():
            self._send_json({"error": "Not found"}, status=404)
            return
        payload = media.fetch_image(filename)
        if payload is None:
            self._send_json({"error": "Image introuvable"}, status=404)
            return
        content_type = "image/png"
        if filename.lower().endswith((".jpg", ".jpeg")):
            content_type = "image/jpeg"
        elif filename.lower().endswith(".gif"):
            content_type = "image/gif"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        self.end_headers()
        self.wfile.write(payload)


def int_from_query(query: dict, key: str, default: int) -> int:
    """Int d'un paramètre de requête, ``default`` si absent/illisible."""
    value = (query.get(key) or [None])[0]
    try:
        return int(value) if value is not None else default
    except ValueError:
        return default
