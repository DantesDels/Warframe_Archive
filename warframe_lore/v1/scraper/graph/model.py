"""Build a lightweight relation graph from workspace state."""

from __future__ import annotations

from typing import Any


def build_graph(
    workspace: Any, *, universe_id: str | None = None
) -> dict[str, Any]:
    """Return nodes and edges describing universe/source/document relations."""
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    for universe in workspace.universes():
        uid = str(universe.get("id", ""))
        if universe_id and uid != universe_id:
            continue
        nodes.append(_node("Universe", uid, universe.get("name", uid), {}))
        _add_children(nodes, edges, uid, workspace)
    return {"nodes": _unique_nodes(nodes), "edges": _unique_edges(edges)}


_MAX_GRAPH_ITEMS_PER_KIND = 120


def _add_children(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    uid: str,
    workspace: Any,
) -> None:
    for src in workspace.sources_for(uid)[:_MAX_GRAPH_ITEMS_PER_KIND]:
        sid = str(src.get("id", ""))
        attrs = {
            "location": src.get("location", ""), "kind": src.get("kind", ""),
            "status": src.get("status", ""), "score": src.get("score", 0),
        }
        title = src.get("title") or src.get("location", "")
        nodes.append(_node("Source", sid, title, attrs))
        edges.append(_edge(f"Universe:{uid}", f"Source:{sid}", "HAS_SOURCE"))
    for doc in workspace.documents_for(uid)[:_MAX_GRAPH_ITEMS_PER_KIND]:
        did, sid = str(doc.get("id", "")), str(doc.get("sourceId", ""))
        attrs = {"url": doc.get("url", ""), "sourceId": sid}
        nodes.append(_node("Document", did, doc.get("title", did), attrs))
        edges.append(_edge(f"Universe:{uid}", f"Document:{did}", "HAS_DOCUMENT"))
        if sid:
            edges.append(_edge(f"Source:{sid}", f"Document:{did}", "PRODUCED"))
    for cand in workspace.candidates_for(uid)[:_MAX_GRAPH_ITEMS_PER_KIND]:
        cid = str(cand.get("id", ""))
        attrs = {"status": cand.get("status", ""), "score": cand.get("score", 0)}
        label = cand.get("title") or cand.get("location", "")
        nodes.append(_node("Candidate", cid, label, attrs))
        edges.append(_edge(f"Universe:{uid}", f"Candidate:{cid}", "HAS_CANDIDATE"))


def _node(
    kind: str, identifier: str, label: Any, attributes: dict[str, Any]
) -> dict[str, Any]:
    return {
        "id": f"{kind}:{identifier}", "kind": kind,
        "label": str(label), "attrs": attributes,
    }


def _edge(source: str, target: str, relation: str) -> dict[str, Any]:
    return {"source": source, "target": target, "type": relation}


def _unique_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    return [n for n in nodes if not (n["id"] in seen or seen.add(n["id"]))]


def _unique_edges(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    out: list[dict[str, Any]] = []
    for edge in edges:
        key = (edge["source"], edge["target"], edge["type"])
        if key not in seen:
            seen.add(key)
            out.append(edge)
    return out
