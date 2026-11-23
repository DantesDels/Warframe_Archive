"""Build the relation graph for one run's exported documents."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .export import export_graph


def write_run_graph(
    out_dir: Path, universe: dict[str, Any], documents: list[dict[str, Any]]
) -> list[Path]:
    """Export universe/source/document relations and return created paths."""
    universe_id = str(universe.get("id", ""))
    root_id = f"Universe:{universe_id}"
    nodes: list[dict[str, Any]] = [
        {
            "id": root_id,
            "kind": "Universe",
            "label": str(universe.get("name", universe_id)),
            "attrs": {},
        }
    ]
    edges: list[dict[str, Any]] = []
    sources: set[str] = set()
    for document in documents:
        source_id = str(document.get("sourceId", ""))
        if source_id:
            source_node = f"Source:{source_id}"
            if source_node not in sources:
                sources.add(source_node)
                nodes.append(
                    {
                        "id": source_node,
                        "kind": "Source",
                        "label": source_id,
                        "attrs": {"location": document.get("url", "")},
                    }
                )
                edges.append(
                    {"source": root_id, "target": source_node, "type": "HAS_SOURCE"}
                )
        document_id = str(document.get("id", ""))
        if document_id:
            document_node = f"Document:{document_id}"
            nodes.append(
                {
                    "id": document_node,
                    "kind": "Document",
                    "label": str(document.get("title", document_id)),
                    "attrs": {
                        "url": document.get("url", ""),
                        "sourceId": source_id,
                    },
                }
            )
            edges.append(
                {"source": root_id, "target": document_node, "type": "HAS_DOCUMENT"}
            )
            if source_id:
                edges.append(
                    {
                        "source": f"Source:{source_id}",
                        "target": document_node,
                        "type": "PRODUCED",
                    }
                )
    return export_graph(out_dir, {"nodes": nodes, "edges": edges})
