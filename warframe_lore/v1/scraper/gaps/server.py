"""Lightweight stdlib local HTTP ingestion server for RAG KnowledgeGaps."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlsplit

from .models import clamp_confidence
from .store import gaps_for, record_gap

_MAX_BODY_BYTES = 256 * 1024


class GapsServerHandle:
    """Handle controlling the background local /gaps HTTP server."""

    def __init__(
        self, server: ThreadingHTTPServer, thread: threading.Thread, url: str
    ) -> None:
        self.server = server
        self.thread = thread
        self.url = url

    def stop(self) -> None:
        """Stop the HTTP server cleanly and join its daemon thread."""
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2.0)


def start_gaps_server(
    workspace: Any,
    *,
    host: str = "127.0.0.1",
    port: int = 8766,
    on_ingested: Any | None = None,
) -> GapsServerHandle:
    """Start a local HTTP endpoint accepting POST /gaps and GET /gaps."""
    lock = threading.Lock()

    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, _fmt: str, *_args: object) -> None:
            return

        def _send_json(self, code: int, body: Any) -> None:
            raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlsplit(self.path)
            if parsed.path == "/health":
                self._send_json(200, {"status": "ok"})
                return
            if parsed.path != "/gaps":
                self._send_json(404, {"error": "not found"})
                return
            params = parse_qs(parsed.query)
            uid = (params.get("universe_id") or [""])[0]
            with lock:
                items = (
                    gaps_for(workspace, uid)
                    if uid
                    else list(workspace.data.get("knowledge_gaps", []))
                )
            self._send_json(200, {"gaps": items, "count": len(items)})

        def do_POST(self) -> None:  # noqa: N802
            if urlsplit(self.path).path != "/gaps":
                self._send_json(404, {"error": "not found"})
                return
            length = int(self.headers.get("Content-Length", "0") or 0)
            if length <= 0 or length > _MAX_BODY_BYTES:
                self._send_json(400, {"error": "invalid payload size"})
                return
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except ValueError:
                self._send_json(400, {"error": "invalid JSON"})
                return
            entries = payload if isinstance(payload, list) else [payload]
            ids: list[str] = []
            with lock:
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    q = str(entry.get("question") or entry.get("query") or "").strip()
                    uid = str(
                        entry.get("universe_id")
                        or entry.get("universeId")
                        or entry.get("universe")
                        or ""
                    ).strip()
                    if not q or not uid:
                        continue
                    gap = record_gap(
                        workspace,
                        uid,
                        q,
                        confidence=clamp_confidence(entry.get("confidence", 0.0)),
                        source=str(entry.get("source") or "bot"),
                        notes=str(entry.get("notes") or ""),
                        append_jsonl=True,
                    )
                    ids.append(gap.id)
            if ids and on_ingested is not None:
                on_ingested(ids)
            self._send_json(201, {"ingested": len(ids), "ids": ids})

    server = ThreadingHTTPServer((host, port), _Handler)
    actual_port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return GapsServerHandle(server, thread, f"http://{host}:{actual_port}/gaps")
