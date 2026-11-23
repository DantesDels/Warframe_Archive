"""Knowledge-graph conversion and GraphRAG bundle exporter."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..graph.html_template import HTML_TEMPLATE
from .models import Entity, Relation, SemanticBundle

KIND_TO_GRAPH = {
    "person": "Person",
    "location": "Location",
    "faction": "Faction",
    "concept": "Concept",
    "timeline": "Timeline",
}


def semantic_to_graph_dict(
    bundle: SemanticBundle | dict[str, Any],
    universe_name: str = "",
) -> dict[str, Any]:
    """Convert a SemanticBundle (or serialized dict) into a visual graph dict."""
    raw = bundle.to_dict() if isinstance(bundle, SemanticBundle) else dict(bundle)
    nodes: list[dict[str, Any]] = []
    node_ids: set[str] = set()
    for ent in raw.get("entities") or []:
        eid = str(ent.get("id", ""))
        if not eid or eid in node_ids:
            continue
        node_ids.add(eid)
        kind = KIND_TO_GRAPH.get(str(ent.get("kind", "concept")).lower(), "Concept")
        nodes.append(
            {
                "id": eid,
                "kind": kind,
                "label": str(ent.get("name", eid)),
                "attrs": {
                    "aliases": list(ent.get("aliases") or []),
                    "taxonomy": list(ent.get("taxonomy") or []),
                    "mentions": int(ent.get("mention_count", 1)),
                    "confidence": round(float(ent.get("confidence", 0.7)), 2),
                    "extractor": str(ent.get("extractor", "rules")),
                    "chunk_ids": list(ent.get("chunk_ids") or [])[:25],
                },
            }
        )
    edges: list[dict[str, Any]] = []
    for rel in raw.get("relations") or []:
        src = str(rel.get("source_id", ""))
        dst = str(rel.get("target_id", ""))
        if src in node_ids and dst in node_ids:
            edges.append(
                {
                    "source": src,
                    "target": dst,
                    "type": str(rel.get("relation_type", "RELATED_TO")),
                    "attrs": {
                        "evidence": str(rel.get("evidence", "")),
                        "chunk_id": str(rel.get("chunk_id", "")),
                        "confidence": round(float(rel.get("confidence", 0.65)), 2),
                        "extractor": str(rel.get("extractor", "rules")),
                    },
                }
            )
    meta = {"mode": "knowledge", "universe": universe_name, **(raw.get("stats") or {})}
    return {"nodes": nodes, "edges": edges, "meta": meta}


def export_graphrag_bundle(
    out_dir: Path,
    universe: dict[str, Any],
    bundle: SemanticBundle,
) -> list[Path]:
    """Export GraphRAG JSONL tables, chunk-linked bundle and HTML knowledge graph."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    paths.append(_write_jsonl(out_dir / "entities.jsonl", bundle.entities))
    paths.append(_write_jsonl(out_dir / "relations.jsonl", bundle.relations))
    paths.append(_write_jsonl(out_dir / "mentions.jsonl", bundle.mentions))

    chunk_links = {e.id: list(e.chunk_ids) for e in bundle.entities if e.chunk_ids}
    bundle_payload = {
        "schema_version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "universe": {"id": universe.get("id"), "name": universe.get("name")},
        "stats": dict(bundle.stats),
        "taxonomy": dict(bundle.taxonomy),
        "chunk_links": chunk_links,
        "files": [
            "entities.jsonl",
            "relations.jsonl",
            "mentions.jsonl",
            "knowledge_graph.json",
            "knowledge_graph.html",
        ],
    }
    bundle_path = out_dir / "graphrag_bundle.json"
    bundle_path.write_text(
        json.dumps(bundle_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    paths.append(bundle_path)

    graph = semantic_to_graph_dict(bundle, str(universe.get("name", "")))
    kg_json = out_dir / "knowledge_graph.json"
    kg_json.write_text(
        json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    kg_html = out_dir / "knowledge_graph.html"
    kg_html.write_text(
        HTML_TEMPLATE.replace("__GRAPH_DATA__", json.dumps(graph, ensure_ascii=False)),
        encoding="utf-8",
    )
    paths.extend([kg_json, kg_html])
    return paths


def _write_jsonl(path: Path, items: list[Entity] | list[Relation] | list[Any]) -> Path:
    lines = [json.dumps(item.to_dict(), ensure_ascii=False) for item in items]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
