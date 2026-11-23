"""Strawberry GraphQL schema over the v1 workspace graph."""

from __future__ import annotations

from typing import Any

import strawberry


@strawberry.type
class GraphAttr:
    key: str
    value: str


@strawberry.type
class GraphNode:
    id: str
    kind: str
    label: str
    attrs: list[GraphAttr]


@strawberry.type
class GraphEdge:
    source: str
    target: str
    type: str


@strawberry.type
class Graph:
    nodes: list[GraphNode]
    edges: list[GraphEdge]


def build_schema(workspace: Any) -> Any:
    """Return a Strawberry schema exposing workspace relations."""

    def _graph(universe_id: str | None = None) -> Graph:
        from .model import build_graph

        result = build_graph(workspace, universe_id=universe_id)
        nodes = [
            GraphNode(
                id=str(node["id"]),
                kind=str(node["kind"]),
                label=str(node["label"]),
                attrs=[
                    GraphAttr(key=str(key), value=str(value))
                    for key, value in (node.get("attrs") or {}).items()
                ],
            )
            for node in result["nodes"]
        ]
        edges = [
            GraphEdge(
                source=str(edge["source"]),
                target=str(edge["target"]),
                type=str(edge["type"]),
            )
            for edge in result["edges"]
        ]
        return Graph(nodes=nodes, edges=edges)

    @strawberry.type
    class Query:
        @strawberry.field
        def graph(self, universe_id: str | None = None) -> Graph:
            return _graph(universe_id)

        @strawberry.field
        def universes(self) -> list[GraphNode]:
            return _graph().nodes

    return strawberry.Schema(query=Query)
