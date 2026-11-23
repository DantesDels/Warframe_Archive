"""Graph model, GraphQL schema and offline visualization for v1."""

from __future__ import annotations

from typing import Any

from .export import export_graph
from .model import build_graph


def build_schema(workspace: Any) -> Any:
    """Lazily build the GraphQL schema (requires the optional strawberry dep)."""
    from .schema import build_schema as build_schema_impl

    return build_schema_impl(workspace)


__all__ = ["build_graph", "build_schema", "export_graph"]
