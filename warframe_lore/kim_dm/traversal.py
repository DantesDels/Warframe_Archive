"""Projections de consultation d'un ``_DialogueFile`` : graphe/messages/script.

Fonctions pures prenant le parseur en argument (aucun état partagé).  Les
parcours sont itératifs — pas de plafond de profondeur ni de récursion Python
sur les cycles du graphe natif.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from warframe_lore.kim_dm.parser import _DialogueFile


def build_graph(parser: "_DialogueFile", start: dict) -> dict:
    """Graphe complet atteignable depuis un nœud de départ natif."""
    visible: dict[int, dict] = {}
    edges: list[dict] = []
    stack = [start["Id"]]
    while stack:
        current = stack.pop()
        if current in visible:
            continue
        node = parser.index[current]
        visible[current] = parser._visible(node)
        outgoing = parser._edges(node)
        edges.extend(outgoing)
        stack.extend(int(edge["target"][2:]) for edge in reversed(outgoing))
    return {"rootId": f"dm{start['Id']}",
            "nodes": list(visible.values()), "edges": edges}


def build_messages(parser: "_DialogueFile", start: dict) -> list[dict]:
    """DFS itératif des répliques, sans plafond ni récursion sur les cycles."""
    lines: list[dict] = []
    visited: set[int] = set()
    stack = [start["Id"]]
    while stack:
        current = stack.pop()
        if current in visited:
            continue
        visited.add(current)
        node = parser.index[current]
        kind = parser.kind(node)
        if kind in ("npc", "choice"):
            visible = parser._visible(node)
            if visible["text"]:
                lines.append({"index": len(lines) + 1,
                              "speaker": visible["speaker"],
                              "text": visible["text"],
                              "player": visible["player"],
                              # Une entrée = une réplique : découpé par
                              # le front pour aérer l'affichage du chat.
                              "lines": [ln.strip() for ln in
                                        visible["text"].split("\n")
                                        if ln.strip()]})
        if kind != "end":
            stack.extend(reversed(parser._child_ids(node)))
    return lines


def build_script(parser: "_DialogueFile", start: dict) -> list[dict]:
    """Projection linéaire existante : première branche, choix en prompt.

    Les actions sont traversées, jamais émises comme répliques PNJ.
    Aucun état ni résultat de condition n'est simulé.
    """
    steps: list[dict] = []
    visited: set[int] = set()
    current = start["Id"]
    while current not in visited:
        visited.add(current)
        node = parser.index[current]
        kind = parser.kind(node)
        if kind == "end":
            if steps:
                steps[-1]["ends"] = True
            break
        if kind == "npc":
            visible = parser._visible(node)
            if visible["text"]:
                steps.append({"kind": "npc", "speaker": visible["speaker"],
                              "text": visible["text"], "player": False,
                              "ends": False, "jump_to": None})
        children = parser._child_ids(node)
        choices = [parser.index[nid] for nid in children
                   if parser.kind(parser.index[nid]) == "choice"]
        if choices:
            options = []
            for choice in choices:
                text = parser._visible(choice)["text"]
                if text:
                    options.append({"text": text, "ends": False})
            steps.append({"kind": "prompt", "options": options or None,
                          "ends": False, "jump_to": None})
            # La continuation suit toujours le premier choix, sans état.
            children = [choices[0]["Id"]]
        if not children:
            if steps:
                steps[-1]["ends"] = True
            break
        current = children[0]
    return steps