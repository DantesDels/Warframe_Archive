"""Construction des graphes de conversation (vue flowchart vue-flow).

Responsabilité unique : depuis le Markdown d'une page de dialogue, produire
``{nodes, edges}`` (nœuds PNJ/joueur/mixtes, arêtes de flux + sauts).
"""

from __future__ import annotations

import re

from ...kim_dm import _anchor_graph
from .dialogue import (
    _BLOCKQUOTE_SPEAKER,
    _CONVO_ENDS,
    _JUMP_ABOVE,
    _JUMP_BELOW,
    _KIM_POINTER_LINE,
    clean_kim_text,
    is_player_speaker,
    normalise_ref,
)


def nodes_id_last_terminal(nodes: list[dict], nid: str) -> bool:
    """Vrai si le nœud ``nid`` est marqué terminal (``{Convo. ends}``)."""
    for node in nodes:
        if node["id"] == nid:
            return bool(node.get("terminal"))
    return False


def build_dialogue_graph(content: str, root_label: str | None = None) -> dict:
    """Construit le graphe de conversation (nœuds + arêtes) d'une page KIM.

    Sémantique des nœuds :
        * nœud PNJ   -> ``speaker`` = nom du personnage (bordure bleue).
        * nœud joueur-> ``player`` = True (choix ``> >``, bordure rouge).
        * nœud mixte (``> texte`` anonyme, continuation) -> pas de locuteur.
        * ``root_label`` (optionnel) -> un nœud-système unique est injecté en
          tête (``_anchor_graph``) : tous les nœuds sans arête entrante y sont
          rattachés (racine unique, pyramide TB).

    Sémantique des arêtes :
        * flux séquentiel normal d'un nœud vers le suivant ;
        * chaque choix ``> >`` est une OPTION qui part du dernier nœud PNJ ;
        * ``{Convo. ends}`` marque un nœud terminal (plus d'arête sortante) ;
        * annotations ``[Continues/Same as above...]`` / ``[Goes the same as
          below choice]`` ajoutent des arêtes de saut vers le nœud référencé.
    """
    lines = content.splitlines()
    nodes: list[dict] = []
    edges: list[dict] = []
    by_text: dict[str, str] = {}   # texte normalisé -> id de nœud (récits)
    last_npc: str | None = None     # dernier nœud PNJ
    pending_choices: list[str] = []  # options en attente de la suite PNJ
    in_preamble = True  # skip la "note d'en-tête" (spoilers, description)

    def add_node(kind: str, speaker: str, text: str, player: bool) -> str:
        prefix = "c_" if kind == "choice" else "n_"
        nid = f"{prefix}{len(nodes)}"
        ends = bool(_CONVO_ENDS.search(text))
        scrubbed = clean_kim_text(_CONVO_ENDS.sub("", text))
        nodes.append({
            "id": nid,
            "speaker": clean_kim_text(speaker),
            "text": scrubbed,
            "player": player,
            "terminal": ends,
        })
        key = normalise_ref(text)
        if key and key not in by_text:
            by_text[key] = nid
        return nid

    def link(source: str, target: str, label: str = "", force: bool = False) -> None:
        if not source or not target or source == target:
            return
        # Un nœud terminal (``{Convo. ends}``) n'a jamais d'arête sortante,
        # SAUF vers les options du joueur qui le suivent (``force=True``) :
        # sinon ces choix deviennent des racines orphelines dans le layout.
        if not force and nodes_id_last_terminal(nodes, source):
            return
        edges.append({"source": source, "target": target, "label": label})

    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            continue
        # Saute le préambule (notes d'en-tête) jusqu'à la première section
        # ``##``/``###`` qui commence la conversation.
        if in_preamble:
            if stripped.startswith("## ") or stripped.startswith("### "):
                in_preamble = False
            else:
                continue
        ann = _JUMP_ABOVE.search(stripped)
        if ann:
            target = by_text.get(normalise_ref(ann.group("ref")))
            if target and last_npc:
                link(last_npc, target, "↻")
            continue
        if _JUMP_BELOW.search(stripped):
            continue

        # Pointeur de navigation KIM (``{Continues/Same/Jump ...}``) : le
        # contenu répète la branche référencée -> ligne ignorée.
        if _KIM_POINTER_LINE.match(stripped):
            continue

        match = _BLOCKQUOTE_SPEAKER.match(stripped)
        if match:
            speaker = match.group("speaker").strip()
            text = match.group("text").strip()
            nid = add_node("npc", speaker, text,
                           player=is_player_speaker(speaker))
            # Les options en attente se rejoignent sur cette nouvelle réplique.
            for opt in pending_choices:
                link(opt, nid)
            had_choices = bool(pending_choices)
            pending_choices = []
            # Pas d'arête directe quand des options étaient en attente : la
            # continuité passe par les choix (sinon arête de contournement).
            if (last_npc and not had_choices
                    and not nodes_id_last_terminal(nodes, last_npc)):
                link(last_npc, nid)
            last_npc = nid
            continue

        nested = re.match(r"^>\s*>\s*(?P<text>.+)$", stripped)
        if nested:
            nid = add_node("choice", "", nested.group("text").strip(), player=True)
            origin = last_npc
            if origin:
                link(origin, nid, force=True)
            elif pending_choices:
                link(pending_choices[-1], nid)
            pending_choices.append(nid)
            continue

        if stripped.startswith("> "):
            text = stripped[2:].strip()
            if text:
                nid = add_node("npc", "", text, player=False)
                for opt in pending_choices:
                    link(opt, nid)
                had_choices = bool(pending_choices)
                pending_choices = []
                # Pas d'arête directe quand des options étaient en attente.
                if (last_npc and not had_choices
                        and not nodes_id_last_terminal(nodes, last_npc)):
                    link(last_npc, nid)
                last_npc = nid

    graph = {"nodes": nodes, "edges": edges}
    if root_label:
        graph = _anchor_graph(nodes, edges, root_label)
    return graph
