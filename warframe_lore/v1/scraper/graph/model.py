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


def _add_children(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    universe_id: str,
    workspace: Any,
) -> None:
    for source in workspace.sources_for(universe_id):
        source_id = str(source.get("id", ""))
        nodes.append(
            _node(
                "Source",
                source_id,
                source.get("title") or source.get("location", ""),
                {"location": source.get("location", "")},
            )
        )
        edges.append(
            _edge(
                f"Universe:{universe_id}",
                f"Source:{source_id}",
                "HAS_SOURCE",
            )
        )
    for document in workspace.documents_for(universe_id):
        document_id = str(document.get("id", ""))
        source_id = str(document.get("sourceId", ""))
        nodes.append(
            _node(
                "Document",
                document_id,
                document.get("title", document_id),
                {"url": document.get("url", ""), "sourceId": source_id},
            )
        )
        edges.append(
            _edge(
                f"Universe:{universe_id}",
                f"Document:{document_id}",
                "HAS_DOCUMENT",
            )
        )
        if source_id:
            edges.append(
                _edge(f"Source:{source_id}", f"Document:{document_id}", "PRODUCED")
            )
    for candidate in workspace.candidates_for(universe_id):
        candidate_id = str(candidate.get("id", ""))
        nodes.append(
            _node(
                "Candidate",
                candidate_id,
                candidate.get("title") or candidate.get("location", ""),
                {
                    "status": candidate.get("status", ""),
                    "score": candidate.get("score", 0),
                },
            )
        )
        edges.append(
            _edge(
                f"Universe:{universe_id}",
                f"Candidate:{candidate_id}",
                "HAS_CANDIDATE",
            )
        )


def _node(
    kind: str, identifier: str, label: Any, attributes: dict[str, Any]
) -> dict[str, Any]:
    return {
        "id": f"{kind}:{identifier}",
        "kind": kind,
        "label": str(label),
        "attrs": attributes,
    }


def _edge(source: str, target: str, relation: str) -> dict[str, Any]:
    return {"source": source, "target": target, "type": relation}


def _unique_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for node in nodes:
        if node["id"] not in seen:
            seen.add(node["id"])
            unique.append(node)
    return unique


def _unique_edges(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    unique: list[dict[str, Any]] = []
    for edge in edges:
        key = (edge["source"], edge["target"], edge["type"])
        if key not in seen:
            seen.add(key)
            unique.append(edge)
    return unique
