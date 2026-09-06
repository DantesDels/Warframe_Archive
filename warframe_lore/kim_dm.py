"""Datamine du Terminal KIM (miroir des fichiers de dialogue JSON du jeu).

Les pages « Kinemantik Instant Messenger » du wiki sont des retranscriptions
humaines ; leurs branches sont incomplètes (sauts ``[Continues as above…]``)
et leur structure repose sur des titres de section.  Les fichiers de datamine
publiés par le projet open-source ``Sainan/warframe-kim-dialogues`` — les
mêmes données que celles servies par browse.wf — contiennent le graphe nodal
**exact** du jeu (``[Char]Dialogue_rom.dialogue.json``) ainsi que le texte
localisé de chaque ligne (``dicts/en.json`` / ``dicts/fr.json``).

Ce module :

    * télécharge et met en cache ce miroir (``mirror_kim_dm``) ;
    * reconstruit par personnage l'arborescence exacte des conversations
      (``parse_dialogue_file``) :

        * chaque ``StartDialogueNode`` -> une conversation (id = ``Content``,
          ex: ``ArthurRank1Convo1``, ``ArthurAmirHack``) ;
        * les nœuds ``DialogueNode`` (messages) et
          ``PlayerChoiceDialogueNode`` (choix du joueur) portent leur texte
          localisé via ``LocTag`` / ``Speaker`` ;
        * les nœuds logiques (booléens, chimie…) sont élidés : leurs arêtes
          (``Outgoing``, ``TrueNodes``/``FalseNodes``, ``Outputs``…) sont
          repliées pour relier directement les nœuds visibles.

Structure d'une conversation : ``{id, title, rank, source, graph, messages,
script}`` avec :

    * ``graph``: ``{nodes, edges}`` — ``nodes`` = ``{id, kind, speaker, text,
      player, terminal}`` où ``kind`` ∈ ``start`` | ``npc`` | ``choice`` |
      ``end`` ; ``edges`` = ``{source, target, label}`` ;
    * ``messages``: liste linéaire ``{index, speaker, text, player}``
      (parcours DFS du graphe, choix compris) ;
    * ``script``: étapes du simulateur ``{kind: "npc"|"prompt", speaker,
      text, player, options, ends, jump_to}`` (marche sur la première
      branche, options regroupées en ``prompt``).
"""

from __future__ import annotations

import json
import re
import time
import urllib.request
from pathlib import Path
from typing import Any

REPO = "Sainan/warframe-kim-dialogues"
BRANCH = "senpai"
RAW_BASE = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/"

# Fichiers de dialogue du jeu par personnage (dossier ``data/`` du miroir).
# Les stubs ``MinervaDialogue``/``VelimirDialogue`` (782 o) redirigent vers la
# conversation combinée ``MinVel*`` : on les télécharge (miroir complet) mais
# ils n'exposent aucune donnée propre.
DIALOGUE_FILES = (
    "AoiDialogue_rom.dialogue.json",
    "ArthurDialogue_rom.dialogue.json",
    "EleanorDialogue_rom.dialogue.json",
    "FlareDialogue_rom.dialogue.json",
    "HexDialogue_rom.dialogue.json",
    "JabirDialogue_rom.dialogue.json",
    "KayaDialogue_rom.dialogue.json",
    "LettieDialogue_rom.dialogue.json",
    "LoidDialogue_rom.dialogue.json",
    "LyonDialogue_rom.dialogue.json",
    "MarieDialogue_rom.dialogue.json",
    "MinervaDialogue_rom.dialogue.json",
    "MinervaVelemirDialogue_rom.dialogue.json",
    "QuincyDialogue_rom.dialogue.json",
    "RoatheDialogue_rom.dialogue.json",
    "VelimirDialogue_rom.dialogue.json",
)

DIALECT_FILE_PREFIX = "Dialogue_rom.dialogue.json"

# Page wiki (dernier segment du titre « Kinemantik Instant Messenger/X ») ->
# fichier de datamine correspondant.  Les personnages absents de ce mapping
# (Amir, Fables & Frontiers, stubs Minerva/Velimir) retombent sur l'analyse
# des sections wiki (fallback historique).
WIKI_PAGE_MAP = {
    "Arthur": "Arthur",
    "Aoi": "Aoi",
    "Eleanor": "Eleanor",
    "Flare": "Flare",
    "Kaya": "Kaya",
    "Leticia": "Lettie",
    "Loid": "Loid",
    "Lyon": "Lyon",
    "Marie": "Marie",
    "Quincy": "Quincy",
    "Roathe": "Roathe",
    "Minerva, Velimir": "MinervaVelemir",
}

DATA_DIRNAME = "data"
DICTS_DIRNAME = "dicts"
SUPPORTED_LANGS = ("de", "en", "es", "fr", "it", "ja", "ko", "pl", "pt",
                   "ru", "tc", "th", "tr", "uk", "zh")

# Marqueurs KIM retirés du texte d'une réplique (mêmes règles que le serveur).
_KIM_INLINE_NAV = re.compile(
    r"\{(?!.*\bends\b)[^{}\n]*?(?:continues?|contiue|same|goes|jump)[^{}\n]*\}",
    re.I)
_KIM_CONDITION_MARK = re.compile(r"\{\s*if\s+[^{}]*\}", re.I)
_KIM_POSITION_MARK = re.compile(r"\{P\d+\}", re.I)

# Type exact des nœuds de message (tout autre ``*DialogueNode`` est un nœud
# logique : Check/Set/Reset/Chemistry/… — à élider, pas à afficher).
_NPC_TYPE = "/EE/Types/Engine/DialogueNode"

_USER_AGENT = "WarframeLoreScraper/1.0 (kim datamine mirror; local tool)"


def _scrub_text(text: str) -> str:
    """Nettoie une réplique (marqueurs KIM, espaces superflus)."""
    if not text:
        return ""
    cleaned = _KIM_INLINE_NAV.sub("", text)
    cleaned = _KIM_CONDITION_MARK.sub("", cleaned)
    cleaned = _KIM_POSITION_MARK.sub("", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


# ------------------------------------------------------------------- miroir
def _download(url: str, target: Path, *, timeout: float = 60.0) -> None:
    """Télécharge ``url`` vers ``target`` (UA + retries simples)."""
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                if response.status != 200:
                    raise OSError(f"HTTP {response.status}")
                target.write_bytes(response.read())
            return
        except Exception as exc:  # noqa: BLE001  (repli après retries)
            last_error = exc
            time.sleep(0.5 * (attempt + 1))
    raise OSError(f"Échec du téléchargement de {url}: {last_error}")


def mirror_kim_dm(output_dir: Path, *, langs: tuple[str, ...] = ("en",),
                  force: bool = False) -> tuple[list[str], list[str]]:
    """Télécharge le miroir KIM (graphes + dictionnaires) dans ``out/kim_dm``.

    Retourne ``(téléchargés, échecs)`` — jamais d'exception pour un fichier
    isolé : les fichiers introuvables n'interrompent pas le reste du miroir.
    """
    root = Path(output_dir) / "kim_dm"
    downloaded: list[str] = []
    failed: list[str] = []
    for subdir in (DATA_DIRNAME, DICTS_DIRNAME):
        (root / subdir).mkdir(parents=True, exist_ok=True)

    def _mirror_file(rel: str) -> None:
        target = root / rel
        if not force and target.is_file():
            return
        try:
            _download(RAW_BASE + rel, target)
            downloaded.append(rel)
        except OSError as exc:
            failed.append(f"{rel} ({exc})")

    for lang in langs:
        _mirror_file(f"{DICTS_DIRNAME}/{lang}.json")
    for filename in DIALOGUE_FILES:
        _mirror_file(f"{DATA_DIRNAME}/{filename}")
    return downloaded, failed


# ------------------------------------------------------------------ parsing
def _node_kind(node: dict) -> str | None:
    """Type visible d'un nœud, ou ``None`` si c'est un nœud logique à élider."""
    node_type = node.get("type", "")
    if node_type == _NPC_TYPE:
        return "npc"
    if node_type.endswith("StartDialogueNode"):
        return "start"
    if node_type.endswith("PlayerChoiceDialogueNode"):
        return "choice"
    if node_type.endswith("EndDialogueNode"):
        return "end"
    # Nœuds d'ÉTAT (écritures d'état vues comme des popups dans le jeu) :
    # +10 Chemistry, « NameFuture is now true », reset de booléen.  Ils font
    # le PONT entre deux répliques et restent dans l'arbre (nœuds-système).
    if node_type.endswith(("ChemistryDialogueNode", "SetBooleanDialogueNode",
                           "ResetBooleanDialogueNode")):
        return "system"
    return None


def _system_text(node: dict) -> str:
    """Libellé court d'un nœud d'état (Chemical/Bool), façon popup du jeu."""
    node_type = node.get("type", "")
    if node_type.endswith("ChemistryDialogueNode"):
        delta = node.get("ChemistryDelta")
        if isinstance(delta, int):
            return f"{delta:+d} Chemistry"
        return "Chemistry"
    content = str(node.get("Content") or "").strip()
    if node_type.endswith("SetBooleanDialogueNode"):
        return f"{content} is now true" if content else "Boolean set"
    if node_type.endswith("ResetBooleanDialogueNode"):
        return f"{content} reset" if content else "Boolean reset"
    return "System"


def _iter_exit_ids(node: dict) -> list[int]:
    """Arêtes sortantes d'un nœud (toutes les formes possibles)."""
    exits = list(node.get("Outgoing") or [])
    exits += list(node.get("TrueNodes") or [])
    exits += list(node.get("FalseNodes") or [])
    for output in node.get("Outputs") or []:
        exits += list(output.get("Outgoing") or [])
    seen: list[int] = []
    for nid in exits:
        if isinstance(nid, int) and nid not in seen:
            seen.append(nid)
    return seen


def _rank_from_id(conv_id: str) -> str:
    match = re.search(r"Rank\s*(\d+)", conv_id, re.I)
    return f"Rank {match.group(1)}" if match else ""


def _dedupe_edges(graph: dict) -> dict:
    seen: set[tuple[str, str]] = set()
    edges: list[dict] = []
    for edge in graph["edges"]:
        key = (edge["source"], edge["target"])
        if key in seen:
            continue
        seen.add(key)
        edges.append(edge)
    return {"nodes": graph["nodes"], "edges": edges}


def _anchor_graph(nodes: list, edges: list, root_label: str,
                  force: bool = True) -> dict:
    """Fait du graphe un arbre à racine (ancre système) unique.

    Injecte un nœud-système ``root`` (l'« ancre » typique du SVG de référence,
    ex. ``AmirRank1Convo1 begins``) et y rattache TOUS les nœuds qui n'ont
    aucune arête entrante : c'est ainsi le seul nœud sans ``target``.
    ``force=False`` n'ajoute l'ancre que s'il existe au moins deux racines
    (cas des unions de conversations) ; par défaut l'ancre est toujours posée.
    """
    if not nodes:
        return {"nodes": [], "edges": edges}
    roots = {n["id"] for n in nodes} - {e["target"] for e in edges}
    if not force and len(roots) <= 1:
        return {"nodes": nodes, "edges": edges}
    root_node = {"id": "root", "kind": "start", "speaker": "",
                 "text": root_label, "player": False, "terminal": False}
    extra = [{"source": "root", "target": nid, "label": ""}
             for nid in sorted(roots) if nid != "root"]
    return _dedupe_edges({"nodes": [root_node] + nodes,
                          "edges": edges + extra})


def _merge_graphs(graphs: list[dict]) -> dict:
    """Union des graphes d'une page (ids de nœuds uniques par fichier)."""
    nodes: list[dict] = []
    edges: list[dict] = []
    seen_nodes: set[str] = set()
    seen_edges: set[tuple[str, str]] = set()
    for graph in graphs:
        for node in graph.get("nodes", []):
            if node["id"] not in seen_nodes:
                seen_nodes.add(node["id"])
                nodes.append(node)
        for edge in graph.get("edges", []):
            key = (edge["source"], edge["target"])
            if key not in seen_edges and edge["source"] in seen_nodes:
                seen_edges.add(key)
                edges.append(edge)
    return {"nodes": nodes, "edges": edges}


class _DialogueFile:
    """Parseur d'un ``[Char]Dialogue_rom.dialogue.json`` (graphe + texte)."""

    def __init__(self, nodes: list[dict], text: dict[str, str]) -> None:
        self.text = text
        self.index: dict[int, dict] = {}
        self.starts: list[dict] = []
        for node in nodes:
            if not isinstance(node, dict) or "Id" not in node:
                continue
            node_id = node["Id"]
            self.index[node_id] = node
            if _node_kind(node) == "start":
                self.starts.append(node)

    # ------------------------------------------------------- utilitaires
    def _visible(self, node: dict, start_label: str) -> dict:
        kind = _node_kind(node)
        if kind == "start":
            begin_label = f"{start_label} begins" if start_label else ""
            return {"id": f"dm{node['Id']}", "kind": "start", "speaker": "",
                    "text": begin_label, "player": False, "terminal": False}
        if kind == "end":
            return {"id": f"dm{node['Id']}", "kind": "end", "speaker": "",
                    "text": "", "player": False, "terminal": True}
        if kind == "system":
            node_type = node.get("type", "")
            return {"id": f"dm{node['Id']}", "kind": "system", "speaker": "",
                    "text": _system_text(node), "player": False,
                    "terminal": False,
                    "km": "chem" if node_type.endswith("ChemistryDialogueNode")
                    else "bool"}
        if kind in ("npc", "choice"):
            loc = node.get("LocTag", "") or ""
            return {
                "id": f"dm{node['Id']}",
                "kind": kind,
                "speaker": _scrub_text(node.get("Speaker", "") or ""),
                "text": _scrub_text(self._text_of(loc)),
                "player": kind == "choice",
                "terminal": False,
            }
        return {"id": f"dm{node['Id']}", "kind": "end", "speaker": "",
                "text": "", "player": False, "terminal": True}

    def _text_of(self, loc: str) -> str:
        return self.text.get(loc, loc)

    def _collapse(self, target_id: int, seen: set[int]) -> list[dict]:
        """Replie les nœuds logiques : nœuds visibles atteints depuis
        ``target_id`` (dérivation exclusive TrueNodes/FalseNodes/Outputs)."""
        if target_id in seen or len(seen) > 80:
            return []
        node = self.index.get(target_id)
        if node is None:
            return []
        kind = _node_kind(node)
        if kind is not None:
            return [self._visible(node, "")]
        exits = _iter_exit_ids(node)
        if not exits:
            return []
        seen = seen | {target_id}
        out: list[dict] = []
        for nid in exits:
            for sub in self._collapse(nid, seen):
                if sub not in out:
                    out.append(sub)
        return out

    def child_nodes(self, node: dict) -> list[dict]:
        """Premiers nœuds visibles atteints depuis ``node`` (ordre exits)."""
        out: list[dict] = []
        for exit_id in _iter_exit_ids(node):
            for sub in self._collapse(exit_id, set()):
                if sub["id"] not in [o["id"] for o in out]:
                    out.append(sub)
        return out

    def child_ids(self, node: dict) -> list[str]:
        return [child["id"] for child in self.child_nodes(node)]

    @staticmethod
    def _pick_first_text(children: list[dict]) -> dict | None:
        """Meilleur enfant à suivre : premier qui porte du texte."""
        if not children:
            return None
        for child in children:
            if child.get("text"):
                return child
        return children[0]

    # ------------------------------------------------------------- graphe
    def graph(self, start: dict) -> dict:
        start_label = str(start.get("Content") or "").strip()
        visible: dict[int, dict] = {}
        edges: list[dict] = []
        visited: set[int] = set()
        stack: list[int] = [start["Id"]]
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            node = self.index.get(current)
            if node is None or _node_kind(node) is None:
                continue
            current_visible = self._visible(node, start_label)
            visible[current] = current_visible
            if current_visible["terminal"]:
                continue
            for target in self._collapse_all_exits(node):
                if target["id"] == current_visible["id"]:
                    continue
                edges.append({"source": current_visible["id"],
                              "target": target["id"], "label": ""})
                self._push_raw(stack, target["id"])
        nodes = [visible[nid] for nid in sorted(visible)]
        return _dedupe_edges({"nodes": nodes, "edges": edges})

    def _collapse_all_exits(self, node: dict) -> list[dict]:
        out: list[dict] = []
        for exit_id in _iter_exit_ids(node):
            for sub in self._collapse(exit_id, set()):
                if sub not in out:
                    out.append(sub)
        return out

    @staticmethod
    def _push_raw(stack: list[int], visible_id: str) -> None:
        try:
            stack.append(int(visible_id[2:]))
        except ValueError:
            pass

    # --------------------------------------------------------- messages
    def messages(self, start: dict) -> list[dict]:
        lines: list[dict] = []
        visited: set[int] = set()

        def walk(raw_id: int) -> None:
            if raw_id in visited or len(visited) > 600:
                return
            visited.add(raw_id)
            node = self.index.get(raw_id)
            if node is None:
                return
            kind = _node_kind(node)
            if kind == "start":
                for child in self.child_ids(node):
                    walk(self._int(child))
                return
            if kind in ("npc", "choice"):
                loc = node.get("LocTag", "") or ""
                text = _scrub_text(self._text_of(loc))
                if text:
                    lines.append({
                        "index": len(lines) + 1,
                        "speaker": _scrub_text(node.get("Speaker", "") or ""),
                        "text": text,
                        "player": kind == "choice",
                    })
            if kind == "end":
                return
            for child in self.child_ids(node):
                walk(self._int(child))

        walk(start["Id"])
        return lines

    # ----------------------------------------------------------- script
    def script(self, start: dict) -> list[dict]:
        """Marche linéaire (première branche) du simulateur.

        Après un message, les nœuds de choix frères sont regroupés en une
        étape ``prompt`` ; la continuation part du premier choix.
        """
        steps: list[dict] = []
        visited: set[int] = set()
        current = start["Id"]
        while current not in visited and len(steps) < 800:
            visited.add(current)
            node = self.index.get(current)
            if node is None:
                break
            kind = _node_kind(node)
            if kind == "start":
                children = self.child_nodes(node)
                first = self._pick_first_text(children)
                if first is None:
                    break
                current = self._int(first["id"])
                continue
            if kind == "end":
                if steps:
                    steps[-1]["ends"] = True
                break
            if kind == "choice":
                # Un choix isolé (rare) : on le saute vers sa continuation.
                children = self.child_nodes(node)
                first = self._pick_first_text(children)
                if first is None:
                    break
                current = self._int(first["id"])
                continue
            # kind == npc : message + éventuel prompt de choix suivant.
            loc = node.get("LocTag", "") or ""
            text = _scrub_text(self._text_of(loc))
            children = self.child_nodes(node)
            if text:
                steps.append({
                    "kind": "npc",
                    "speaker": _scrub_text(node.get("Speaker", "") or ""),
                    "text": text,
                    "player": False,
                    "ends": False,
                    "jump_to": None,
                })
            choice_targets = [c for c in children
                              if c["kind"] == "choice"]
            if choice_targets:
                options = []
                follow: str | None = None
                for choice in choice_targets:
                    loc_tag = self.index.get(self._int(choice["id"]))
                    if loc_tag is None:
                        continue
                    choice_loc = loc_tag.get("LocTag", "") or ""
                    option_text = _scrub_text(self._text_of(choice_loc))
                    if option_text:
                        options.append({"text": option_text, "ends": False})
                prompt = {"kind": "prompt", "options": options or None,
                          "ends": False, "jump_to": None}
                for choice in choice_targets:
                    choice_node = self.index.get(self._int(choice["id"]))
                    if choice_node is None:
                        continue
                    continuation = self.child_nodes(choice_node)
                    inner = self._pick_first_text(continuation)
                    if inner is not None:
                        follow = inner["id"]
                        break
                if follow is not None:
                    steps.append(prompt)
                    current = self._int(follow)
                    continue
                steps.append(prompt)
                if not children:
                    break
                first = self._pick_first_text(children)
                if first is None:
                    break
                current = self._int(first["id"])
                continue
            if not children:
                if steps:
                    steps[-1]["ends"] = True
                break
            first = self._pick_first_text(children)
            if first is None:
                break
            current = self._int(first["id"])
        return steps

    def _kind_of(self, raw_id: int) -> str | None:
        node = self.index.get(raw_id)
        return _node_kind(node) if node is not None else None

    @staticmethod
    def _int(visible_id: str) -> int:
        try:
            return int(visible_id[2:])
        except ValueError:
            return -1


def parse_dialogue_file(nodes: list[dict], text: dict[str, str]) -> list[dict]:
    """Reconstruit les conversations d'un ``[Char]Dialogue_rom.dialogue.json``.

    Une conversation par ``StartDialogueNode`` ; les nœuds logiques du fil sont
    repliés pour obtenir un graphe de nœuds visibles (messages/choix/fin).
    """
    parser = _DialogueFile(nodes, text)
    conversations: list[dict] = []
    for start in parser.starts:
        conv_id = str(start.get("Content") or "").strip()
        if not conv_id:
            continue
        conversations.append({
            "id": conv_id,
            "title": conv_id,
            "rank": _rank_from_id(conv_id),
            "source": "dm",
            "graph": parser.graph(start),
            "messages": parser.messages(start),
            "script": parser.script(start),
        })
    conversations.sort(key=lambda c: c["id"])
    return conversations


class KimDM:
    """Graphes KIM reconstruits depuis un miroir de datamine local."""

    def __init__(self, data_dir: Path, dicts_dir: Path) -> None:
        self.data_dir = Path(data_dir)
        self.dicts_dir = Path(dicts_dir)
        self._store: dict[str, dict[str, Any]] = {}
        self.load()

    # ------------------------------------------------------------- miroir
    def available(self) -> bool:
        return bool(self._store)

    def conversations_for(self, wiki_character: str) -> list[dict] | None:
        """Conversations (résumé) d'un personnage exposé, ``None`` sinon."""
        data = self._store.get(wiki_character)
        if not data:
            return None
        return [
            {"id": c["id"], "title": c["title"],
             "rank": c["rank"], "source": "dm"}
            for c in data["conversations"]
        ]

    def conversation(self, wiki_character: str, conv_id: str) -> dict | None:
        data = self._store.get(wiki_character)
        if not data:
            return None
        for c in data["conversations"]:
            if c["id"] == conv_id:
                return c
        return None

    def graph(self, wiki_character: str, conv: str | None = None) -> dict | None:
        """Graphe d'une conversation (ou union de toute la page) — None si
        le personnage n'est pas couvert par le miroir."""
        data = self._store.get(wiki_character)
        if not data:
            return None
        if conv:
            found = self.conversation(wiki_character, conv)
            return found["graph"] if found else None
        merged = _merge_graphs([c["graph"] for c in data["conversations"]])
        return _anchor_graph(merged["nodes"], merged["edges"],
                             f"{wiki_character} — conversations")

    # -------------------------------------------------------------- disque
    def load(self) -> None:
        """Recharge le miroir (conversations + dict) depuis le disque."""
        self._store = {}
        text: dict[str, str] = {}
        for lang in ("en", "fr"):
            if text or not (self.dicts_dir / f"{lang}.json").is_file():
                continue
            text = self._read_dict(lang)
        if not text:
            for lang in SUPPORTED_LANGS:
                text = self._read_dict(lang)
                if text:
                    break

        for wiki_character, stem in WIKI_PAGE_MAP.items():
            path = self.data_dir / f"{stem}{DIALECT_FILE_PREFIX}"
            if not path.is_file():
                continue
            try:
                nodes = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            conversations = parse_dialogue_file(nodes, text)
            if conversations:
                self._store[wiki_character] = {
                    "conversations": conversations,
                    "file": path.name,
                }

    def _read_dict(self, lang: str) -> dict[str, str]:
        path = self.dicts_dir / f"{lang}.json"
        if not path.is_file():
            return {}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        return {k: str(v) for k, v in raw.items() if isinstance(v, str)}