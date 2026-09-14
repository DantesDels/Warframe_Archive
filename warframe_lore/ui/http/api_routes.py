"""The ``/api/*`` routes of the local UI.

Single responsibility: one small function per endpoint, taking the handler (for
emission) and the parsed query — plus the routing table that binds a path to its
function.  Adding an endpoint = one function and one table entry; the dispatcher
in :mod:`handlers` never changes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import unquote

from ...timeline import children_payload, roots_payload
from .media import media_payload
from .payloads import kim_for_query, page_for_query, pages_for_query

if TYPE_CHECKING:
    from .handlers import ApiHandler


def int_from_query(query: dict, key: str, default: int) -> int:
    """Int d'un paramètre de requête, ``default`` si absent/illisible."""
    value = (query.get(key) or [None])[0]
    try:
        return int(value) if value is not None else default
    except ValueError:
        return default


def timeline_roots(handler: ApiHandler, query: dict) -> None:
    handler._send_json(roots_payload())


def timeline_children(handler: ApiHandler, query: dict) -> None:
    parent_id = (query.get("parent_id") or [None])[0]
    if not parent_id:
        handler._send_json({"error": "parent_id manquant"}, status=400)
        return
    payload = children_payload(parent_id)
    if payload is None:
        handler._send_json({"error": "Noeud inconnu"}, status=404)
        return
    handler._send_json(payload)


def stats(handler: ApiHandler, query: dict) -> None:
    handler._send_json(handler.store.stats())


def buckets(handler: ApiHandler, query: dict) -> None:
    handler._send_json(handler.store.list_buckets())


def pages(handler: ApiHandler, query: dict) -> None:
    handler._send_json(pages_for_query(handler.store, query))


def page(handler: ApiHandler, query: dict) -> None:
    handler._send_json(page_for_query(handler.store, query))


def kim(handler: ApiHandler, query: dict) -> None:
    handler._send_json(kim_for_query(handler.store, query))


def graph(handler: ApiHandler, query: dict) -> None:
    title = unquote((query.get("title") or [""])[0])
    conversation = unquote((query.get("conv") or [""])[0])
    handler._send_json(handler.store.kim_graph(title, conversation) or {})


def recent(handler: ApiHandler, query: dict) -> None:
    handler._send_json(handler.store.recent(limit=int_from_query(
        query, "limit", 20)))


def search(handler: ApiHandler, query: dict) -> None:
    handler._send_json(handler.store.search(
        (query.get("q") or [""])[0],
        limit=int_from_query(query, "limit", 50),
        bucket=(query.get("bucket") or [""])[0] or None,
        canon=(query.get("canon") or [""])[0] or None))


def suggest(handler: ApiHandler, query: dict) -> None:
    handler._send_json(handler.store.suggest(
        (query.get("q") or [""])[0], limit=int_from_query(query, "limit", 8)))


def media(handler: ApiHandler, query: dict) -> None:
    handler._send_json(media_payload(handler.store, handler.media))


# Path -> endpoint function (the dispatcher reads this table only).
API_ROUTES = {
    "/api/timeline/roots": timeline_roots,
    "/api/timeline": timeline_children,
    "/api/stats": stats,
    "/api/buckets": buckets,
    "/api/pages": pages,
    "/api/page": page,
    "/api/kim": kim,
    "/api/graph": graph,
    "/api/recent": recent,
    "/api/search": search,
    "/api/suggest": suggest,
    "/api/media": media,
}

__all__ = ["API_ROUTES", "int_from_query"]
