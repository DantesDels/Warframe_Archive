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
          localisé via ``LocTag`` ou ``Content``, et ``Speaker`` ;
        * tous les nœuds logiques et leurs routes natives sont conservés,
          sans évaluation des conditions ni modification d'état.

Structure d'une conversation : ``{id, title, rank, source, graph, messages,
script}`` avec :

    * ``graph``: ``{rootId, nodes, edges}``, racine native ``dm<Start Id>`` ;
      chaque nœud expose ``id, type, kind, speaker, text, player, terminal``
      (``kind`` : start/npc/choice/chemistry/system/end), avec
      ``chemistryDelta`` pour la chimie et ``locTag`` si présent ;
      chaque arête expose ``id, source, target, label, route`` et
      ``outputIndex`` pour les routes ``Outputs`` ;
    * ``messages``: liste linéaire ``{index, speaker, text, player}``
      (parcours DFS, choix compris, sans actions système) ;
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
# (Fables & Frontiers, stubs Minerva/Velimir) retombent sur l'analyse
# des sections wiki (fallback historique).
WIKI_PAGE_MAP = {
    "Amir": "Jabir",
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

# Seuls les types natifs exacts déterminent le rôle d'un nœud.
_ENGINE = "/EE/Types/Engine/"
_NODE_KINDS = {
    _ENGINE + "StartDialogueNode": "start",
    _ENGINE + "DialogueNode": "npc",
    _ENGINE + "PlayerChoiceDialogueNode": "choice",
    _ENGINE + "ChemistryDialogueNode": "chemistry",
    _ENGINE + "EndDialogueNode": "end",
}

_USER_AGENT = "WarframeLoreScraper/1.0 (kim datamine mirror; local tool)"


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
def _node_kind(node: dict) -> str:
    """Rôle du type natif exact ; les types inconnus restent des systèmes."""
    return _NODE_KINDS.get(node.get("type", ""), "system")


def _rank_from_id(conv_id: str) -> str:
    match = re.search(r"Rank\s*(\d+)", conv_id, re.I)
    return f"Rank {match.group(1)}" if match else ""


def _anchor_graph(nodes: list, edges: list, root_label: str,
                  force: bool = True) -> dict:
    """Ancre synthétique des pages agrégées et du fallback wiki existant.

    Les starts natifs restent rattachés même avec une arête de retour.
    Cette fonction n'est pas utilisée pour une conversation native isolée.
    """
    if not nodes:
        return {"rootId": None, "nodes": [], "edges": edges}
    roots = {n["id"] for n in nodes} - {e["target"] for e in edges}
    roots.update(n["id"] for n in nodes if n.get("kind") == "start")
    if not force and len(roots) <= 1:
        return {"rootId": next(iter(roots), None), "nodes": nodes,
                "edges": edges}
    root_node = {"id": "root", "kind": "start", "speaker": "",
                 "text": root_label, "player": False, "terminal": False}
    extra = [{"id": f"root:Outgoing:{nid}", "source": "root",
              "target": nid, "label": "", "route": "Outgoing"}
             for nid in sorted(roots) if nid != "root"]
    return {"rootId": "root", "nodes": [root_node] + nodes,
            "edges": edges + extra}


def _merge_graphs(graphs: list[dict]) -> dict:
    """Union des graphes d'une page (ids de nœuds uniques par fichier)."""
    nodes: list[dict] = []
    edges: list[dict] = []
    seen_nodes: set[str] = set()
    seen_edges: set[str] = set()
    for graph in graphs:
        for node in graph.get("nodes", []):
            if node["id"] not in seen_nodes:
                seen_nodes.add(node["id"])
                nodes.append(node)
        for edge in graph.get("edges", []):
            key = edge["id"]
            if key not in seen_edges:
                seen_edges.add(key)
                edges.append(edge)
    return {"nodes": nodes, "edges": edges}


class _DialogueFile:
    """Parseur des nœuds natifs ; aucune reconstruction à partir d'Incoming."""

    def __init__(self, nodes: list[dict], text: dict[str, str],
                 sender: str) -> None:
        self.text = text
        self.sender = self._text_of(sender)
        self.index = {
            node["Id"]: node for node in nodes
            if isinstance(node, dict) and type(node.get("Id")) is int
        }
        self.starts = [node for node in self.index.values()
                       if _node_kind(node) == "start"]

    def _text_of(self, value: Any) -> str:
        """Résout une clé du dictionnaire sans altérer le texte natif."""
        value = "" if value is None else str(value)
        return self.text.get(value, value)

    def _system_text(self, node: dict) -> str:
        """Décrit les actions et conditions sans les exécuter."""
        node_type = node.get("type", "")
        content = self._text_of(node.get("Content"))
        if node_type == _ENGINE + "CheckBooleanDialogueNode":
            return f"Check boolean: {content}"
        if node_type in (_ENGINE + "CheckBooleanScriptDialogueNode",
                         _ENGINE + "ScriptDialogueNode"):
            script = node.get("Script") or {}
            action = ("Check script" if node_type == _ENGINE + "CheckBooleanScriptDialogueNode"
                      else "Run script")
            return (f"{action}: {self._text_of(script.get('Script'))}"
                    f" :: {self._text_of(script.get('Function'))}")
        if node_type in (_ENGINE + "CheckMultiBooleanDialogueNode",
                         _ENGINE + "CheckCounterDialogueNode"):
            title = "Check booleans"
            if node_type == _ENGINE + "CheckCounterDialogueNode":
                title = f"Check counter: {self._text_of(node.get('CounterName'))}"
            expressions = [self._text_of(output.get("Expression"))
                           for output in node.get("Outputs") or []]
            return "\n".join([title] + expressions)
        if node_type == _ENGINE + "SetBooleanDialogueNode":
            return f"{content} is now true" if content else "Set boolean to true"
        if node_type == _ENGINE + "ResetBooleanDialogueNode":
            return f"{content} is now false" if content else "Reset boolean to false"
        if node_type == _ENGINE + "IncCounterDialogueNode":
            parts = str(node.get("Content") or "").split(" ")
            if len(parts) == 2:
                try:
                    delta = int(parts[1])
                except ValueError:
                    pass
                else:
                    return f"Increment counter: {self._text_of(parts[0])} {delta:+d}"
            return f"Increment counter: {content}"
        if node_type == _ENGINE + "SpecialCompletionDialogueNode":
            title = "Special completion"
            if "CompletionType" in node:
                title += f" (type {node['CompletionType']})"
            targets = []
            for info in node.get("OtherDialogueInfos") or []:
                tag = self._text_of(info.get("Tag"))
                dialogue = self._text_of(info.get("Dialogue"))
                targets.append(f"{tag} ({dialogue})" if tag and dialogue
                               else tag or dialogue)
            return "\n".join([title] + targets)
        detail = self._text_of(node.get("LocTag") or node.get("Content"))
        title = f"System action: {node_type.rsplit('/', 1)[-1] or 'Unknown type'}"
        return f"{title}\n{detail}" if detail else title

    def _visible(self, node: dict) -> dict:
        kind = _node_kind(node)
        content = self._text_of(node.get("Content"))
        text = self._text_of(node.get("LocTag") or node.get("Content"))
        speaker = self._text_of(node.get("Speaker"))
        if kind == "start":
            text = content
        elif kind == "end":
            text = "Chat finished"
            if content:
                text += f"\nNext conversation: {content}"
        elif kind == "chemistry":
            delta = node.get("ChemistryDelta", 0)
            text = (f"{delta:+} Chemistry" if type(delta) in (int, float)
                    else "Chemistry")
        elif kind == "system":
            text = self._system_text(node)
        elif kind == "choice":
            speaker = "Vous"
        elif kind == "npc" and not speaker:
            speaker = self.sender
        visible = {
            "id": f"dm{node['Id']}", "type": node.get("type", ""),
            "kind": kind, "speaker": speaker, "text": text,
            "player": kind == "choice", "terminal": kind == "end",
        }
        if kind == "chemistry" and type(delta) in (int, float):
            visible["chemistryDelta"] = delta
        if node.get("LocTag"):
            visible["locTag"] = node["LocTag"]
        return visible

    def _edges(self, node: dict) -> list[dict]:
        """Une arête par entrée native, y compris les routes parallèles."""
        routes = [(route, node.get(route) or [], label, None)
                  for route, label in (("Outgoing", ""), ("TrueNodes", "True"),
                                       ("FalseNodes", "False"))]
        routes.extend(("Outputs", output.get("Outgoing") or [],
                       self._text_of(output.get("Expression")), index)
                      for index, output in enumerate(node.get("Outputs") or []))
        edges = []
        source = f"dm{node['Id']}"
        for route, targets, label, output_index in routes:
            for index, target in enumerate(targets):
                if type(target) is not int or target not in self.index:
                    continue
                route_id = route if output_index is None else f"{route}:{output_index}"
                edge = {"id": f"{source}:{route_id}:{index}:dm{target}",
                        "source": source, "target": f"dm{target}",
                        "label": label, "route": route}
                if output_index is not None:
                    edge["outputIndex"] = output_index
                edges.append(edge)
        return edges

    def _child_ids(self, node: dict) -> list[int]:
        return list(dict.fromkeys(int(edge["target"][2:])
                                  for edge in self._edges(node)))

    def graph(self, start: dict) -> dict:
        visible: dict[int, dict] = {}
        edges: list[dict] = []
        stack = [start["Id"]]
        while stack:
            current = stack.pop()
            if current in visible:
                continue
            node = self.index[current]
            visible[current] = self._visible(node)
            outgoing = self._edges(node)
            edges.extend(outgoing)
            stack.extend(int(edge["target"][2:]) for edge in reversed(outgoing))
        return {"rootId": f"dm{start['Id']}",
                "nodes": list(visible.values()), "edges": edges}

    def messages(self, start: dict) -> list[dict]:
        """DFS itératif des répliques, sans plafond ni récursion sur les cycles."""
        lines: list[dict] = []
        visited: set[int] = set()
        stack = [start["Id"]]
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            node = self.index[current]
            kind = _node_kind(node)
            if kind in ("npc", "choice"):
                visible = self._visible(node)
                if visible["text"]:
                    lines.append({"index": len(lines) + 1,
                                  "speaker": visible["speaker"],
                                  "text": visible["text"],
                                  "player": visible["player"]})
            if kind != "end":
                stack.extend(reversed(self._child_ids(node)))
        return lines

    def script(self, start: dict) -> list[dict]:
        """Projection linéaire existante : première branche, choix en prompt.

        Les actions sont traversées, jamais émises comme répliques PNJ.
        Aucun état ni résultat de condition n'est simulé.
        """
        steps: list[dict] = []
        visited: set[int] = set()
        current = start["Id"]
        while current not in visited:
            visited.add(current)
            node = self.index[current]
            kind = _node_kind(node)
            if kind == "end":
                if steps:
                    steps[-1]["ends"] = True
                break
            if kind == "npc":
                visible = self._visible(node)
                if visible["text"]:
                    steps.append({"kind": "npc", "speaker": visible["speaker"],
                                  "text": visible["text"], "player": False,
                                  "ends": False, "jump_to": None})
            children = self._child_ids(node)
            choices = [self.index[nid] for nid in children
                       if _node_kind(self.index[nid]) == "choice"]
            if choices:
                options = []
                for choice in choices:
                    text = self._visible(choice)["text"]
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


def parse_dialogue_file(nodes: list[dict], text: dict[str, str],
                        sender: str = "") -> list[dict]:
    """Reconstruit les conversations d'un ``[Char]Dialogue_rom.dialogue.json``.

    Une conversation par type natif exact ``StartDialogueNode``. Le graphe
    contient tous les IDs atteignables par les seules routes sortantes natives.
    ``sender`` est le nom wiki de repli des PNJ sans Speaker explicite.
    """
    if not isinstance(nodes, list):
        return []
    parser = _DialogueFile(nodes, text, sender)
    conversations: list[dict] = []
    for start in parser.starts:
        conv_id = str(start.get("Content") or "")
        conversations.append({
            "id": conv_id,
            "title": parser._text_of(conv_id),
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
            conversations = parse_dialogue_file(nodes, text, sender=wiki_character)
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
