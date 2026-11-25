"""Index note planning: root MOC and per-folder _Index.md files."""

from __future__ import annotations

from ..blueprint import Blueprint
from ..graph_engine.graph import KnowledgeGraph
from .planning import NotePlan


def index_plans(
    blueprint: Blueprint,
    entity_paths: dict[str, str],
    graph: KnowledgeGraph,
    community_paths: dict[int, tuple[str, str]],
    macro_path: str,
) -> list[NotePlan]:
    """Plan the root MOC and one _Index.md per populated folder."""
    plans: list[NotePlan] = []
    folders: dict[str, list[tuple[str, str]]] = {}
    for entity_id, path in entity_paths.items():
        folder = path.rsplit("/", 1)[0]
        folders.setdefault(folder, []).append((graph.entities[entity_id].name, path))
    for folder, entries in sorted(folders.items()):
        entries.sort()
        body = f"# {folder}\n\n" + "\n".join(
            f"- [[{path}|{name}]]" for name, path in entries
        ) + "\n"
        plans.append(NotePlan(
            f"{folder}/_Index.md", {"entries": entries}, body,
            fields={"id": f"index-{folder}", "type": "index", "aliases": [],
                    "tags": ["index"], "sources_count": 0},
            apply_autolink=False,
        ))
    links = [f"- [[{macro_path}|Vue globale]]"]
    links += [f"- [[{folder}/_Index.md|{folder}]]" for folder in sorted(folders)]
    if graph.analysis:
        labels = {c.id: c.label for c in graph.analysis.communities}
        links += [
            f"- [[{note}|{labels[cid]}]]"
            for cid, (note, _canvas) in sorted(community_paths.items())
        ]
    root = blueprint.vault["root_index"]
    plans.append(NotePlan(
        root, {"links": links}, "# Index\n\n" + "\n".join(links) + "\n",
        fields={"id": "root-index", "type": "index", "aliases": [],
                "tags": ["index"], "sources_count": 0},
        apply_autolink=False,
    ))
    return plans
