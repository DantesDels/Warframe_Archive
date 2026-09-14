"""Timeline (Warframe lore) : lazy-loadable hierarchy and payloads.

Exposes the API contract used by the ``/timeline/`` Vue app:

- ``GET /api/timeline/roots``
      ``{"nodes": [era ...], "edges": [root edges ...]}``
- ``GET /api/timeline?parent_id={id}``
      ``{"nodes": [immediate children ...], "edges": [parent edges ...]}``

``has_children`` is derived from the static tree so the frontend can
render an expansion button and fetch children on demand, depth by depth.

Edges are keyed by the node that loads them (their parent), so endpoints
are always both loaded when the edge is drawn.  Each edge carries a
``paradox`` flag: causal chains (false, solid) vs eternalism links
(true, dashed).
"""

from __future__ import annotations

from ._data import EDGES, NODES

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
        "type": node["type"],
        "codex_slug": node.get("codex_slug"),
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


def edges(parent_id: str = "") -> list[dict]:
    """Edges drawn once ``parent_id`` and its endpoints are loaded."""
    return [dict(e) for e in EDGES.get(parent_id, [])]


def all_edges() -> list[dict]:
    return [dict(e) for group in EDGES.values() for e in group]


def paradox_edges() -> list[dict]:
    return [e for e in all_edges() if e["paradox"]]


def sequel_edges() -> list[dict]:
    return [e for e in all_edges() if not e["paradox"]]


def roots_payload() -> dict:
    return {"nodes": roots(), "edges": edges()}


def children_payload(parent_id: str) -> dict | None:
    """Payload for ``/api/timeline?parent_id=`` or ``None`` (404)."""
    if parent_id not in _ID_NODE:
        return None
    return {"nodes": children(parent_id), "edges": edges(parent_id)}


def graph_payload() -> dict:
    """Flat graph contract ``{nodes, edges}`` (frontend mock / fixtures).

    Nodes carry the runtime-shaped ``expanded`` state (initialized false)
    alongside their public fields.  Edges map the ``paradox`` flag onto the
    wire contract ``type: "canonical" | "paradox"``.  The whole curated
    dataset is exported — no orphan, no weapon.
    """
    nodes_out: list[dict] = []
    for n in all_nodes():
        nodes_out.append({
            "id": n["id"],
            "type": n["type"],
            "label": n["label"],
            "codex_slug": n["codex_slug"],
            "expanded": False,
            "parent_id": n["parent_id"],
            "year": n.get("year", ""),
            "note": n.get("note", ""),
            "has_children": n["has_children"],
        })
    edges_out: list[dict] = []
    for e in all_edges():
        edges_out.append({
            "source": e["source"],
            "target": e["target"],
            "type": "canonical" if not e["paradox"] else "paradox",
            "label": e.get("label", ""),
        })
    return {"nodes": nodes_out, "edges": edges_out}
