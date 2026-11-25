"""Note planning: vault paths, input payloads and frontmatter fields."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from ..blueprint import Blueprint
from ..graph_engine.graph import KnowledgeGraph
from ..scraper.slugs import slugify
from .canvas import community_canvas, macro_canvas
from .notes_macro import macro_payload, render_macro_note
from .notes_meso import community_payload, render_community_note
from .notes_micro import entity_payload, render_entity_note


@dataclass(slots=True)
class NotePlan:
    """One planned vault file with its hashable payload and rendered body."""

    relative_path: str
    payload: dict[str, Any]
    body: str
    fields: dict[str, Any] = field(default_factory=dict)
    apply_autolink: bool = True
    self_name: str = ""


def _entity_paths(graph: KnowledgeGraph, blueprint: Blueprint) -> dict[str, str]:
    paths: dict[str, str] = {}
    used: set[str] = set()
    for entity_id, entity in graph.entities.items():
        folder = blueprint.folder_for(entity.entity_type)
        path = f"{folder}/{slugify(entity.name) or entity_id}.md"
        if path in used:
            path = f"{folder}/{slugify(entity.name)}-{entity_id[-6:]}.md"
        used.add(path)
        paths[entity_id] = path
    return paths


def _community_paths(
    graph: KnowledgeGraph, blueprint: Blueprint
) -> dict[int, tuple[str, str]]:
    folder = blueprint.vault["arcs_folder"]
    paths: dict[int, tuple[str, str]] = {}
    for community in graph.analysis.communities if graph.analysis else []:
        stem = f"{folder}/arc-{community.id}-{slugify(community.label) or community.id}"
        paths[community.id] = (f"{stem}.md", f"{stem}.canvas")
    return paths


def build_plans(graph: KnowledgeGraph, blueprint: Blueprint) -> list[NotePlan]:
    """Plan every vault file: micro, meso, macro, canvases and indexes."""
    entity_paths = _entity_paths(graph, blueprint)
    community_paths = _community_paths(graph, blueprint)
    plans: list[NotePlan] = []
    for entity_id, path in entity_paths.items():
        entity = graph.entities[entity_id]
        payload = entity_payload(graph, entity_id, blueprint)
        plans.append(NotePlan(
            path, payload, render_entity_note(graph, entity_id, blueprint),
            fields={"id": entity_id, "type": entity.entity_type,
                    "aliases": list(entity.aliases), "tags": [entity.entity_type],
                    "sources_count": len(payload["sources"])},
            self_name=entity.name,
        ))
    for community in graph.analysis.communities if graph.analysis else []:
        note_path, canvas_path = community_paths[community.id]
        payload = community_payload(graph, community, blueprint, canvas_path)
        plans.append(NotePlan(
            note_path, payload,
            render_community_note(graph, community, blueprint, canvas_path),
            fields={"id": f"community-{community.id}", "type": "arc",
                    "aliases": [community.label], "tags": ["arc"],
                    "sources_count": len(payload["sources"])},
        ))
        canvas_payload = community_canvas(graph, community, blueprint, entity_paths)
        plans.append(NotePlan(
            canvas_path, canvas_payload,
            json.dumps(canvas_payload, ensure_ascii=False, indent=2) + "\n",
            apply_autolink=False,
        ))
    macro_path = blueprint.vault["macro_note"]
    macro_note_paths = {cid: note for cid, (note, _) in community_paths.items()}
    payload = macro_payload(graph, blueprint, macro_note_paths)
    plans.append(NotePlan(
        macro_path, payload, render_macro_note(graph, blueprint, macro_note_paths),
        fields={"id": "macro", "type": "overview", "aliases": [],
                "tags": ["overview"], "sources_count": len(graph.sources)},
    ))
    macro_canvas_payload = macro_canvas(graph, blueprint, entity_paths)
    plans.append(NotePlan(
        macro_path.rsplit(".md", 1)[0] + ".canvas", macro_canvas_payload,
        json.dumps(macro_canvas_payload, ensure_ascii=False, indent=2) + "\n",
        apply_autolink=False,
    ))
    # Local import: indexes imports NotePlan back from this module.
    from .indexes import index_plans

    plans.extend(
        index_plans(blueprint, entity_paths, graph, community_paths, macro_path)
    )
    return plans
