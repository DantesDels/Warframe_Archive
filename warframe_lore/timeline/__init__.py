"""Timeline (Warframe lore) : lazy-loadable hierarchy and payloads.

Exposes the API contract used by the ``/timeline/`` Vue app:

- ``GET /api/timeline/roots``
      ``{"nodes": [era ...], "edges": [paradox edges ...]}``
- ``GET /api/timeline?parent_id={id}``
      ``{"nodes": [immediate children ...], "edges": []}``

``has_children`` is derived from the static tree so the frontend can
render an expansion button and fetch children on demand, depth by depth.
"""

from __future__ import annotations

from ._data import NODES, PARADOX_EDGES

_PARENT_CHILDREN: dict[str, list[dict]] = {}
_ID_NODE: dict[str, dict] = {}
for _node in NODES:
    _ID_NODE[_node["id"]] = _node
    _PARENT_CHILDREN.setdefault(_node["parent_id"] or "", []).append(_node)


def _has_children(node_id: str) -> bool:
    return bool(_PARENT_CHILDREN.get(node_id))


def _public(node: dict) -> dict:
    """Node payload exposed over the wire (has_children included)."""
    payload = {
        "id": node["id"],
        "parent_id": node["parent_id"],
        "label": node["label"],
        "kind": node["kind"],
        "has_children": _has_children(node["id"]),
    }
    if node.get("year"):
        payload["year"] = node["year"]
    if node.get("note"):
        payload["note"] = node["note"]
    return payload


def roots() -> list[dict]:
    """Top-level eras (parentless nodes)."""
    return [_public(n) for n in _PARENT_CHILDREN.get("", [])]


def children(parent_id: str) -> list[dict] | None:
    """Immediate children of ``parent_id``; ``None`` if unknown."""
    if parent_id not in _ID_NODE:
        return None
    return [_public(n) for n in _PARENT_CHILDREN.get(parent_id, [])]


def node(node_id: str) -> dict | None:
    """Raw internal node (tests / validation)."""
    return _ID_NODE.get(node_id)


def all_nodes() -> list[dict]:
    return [_public(n) for n in NODES]


def paradox_edges() -> list[dict]:
    return list(PARADOX_EDGES)


def roots_payload() -> dict:
    return {"nodes": roots(), "edges": paradox_edges()}


def children_payload(parent_id: str) -> dict | None:
    """Payload for ``/api/timeline?parent_id=`` or ``None`` (404)."""
    if parent_id not in _ID_NODE:
        return None
    return {"nodes": children(parent_id), "edges": []}