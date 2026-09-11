"""Parsing of the ``[Char]Dialogue_rom.dialogue.json`` files (native nodes).

Single responsibility: translate the game's native nodes (``Id``/``Content``/
``Speaker``/outgoing routes) into a conversation structure.  No state is
simulated: actions and conditions are described, never executed.  Read-only
projections (graph/messages/script) live in ``traversal`` —
``_DialogueFile`` only exposes the node index and their visible rendering.
"""

from __future__ import annotations

import re
from typing import Any

from warframe_lore.kim_dm.constants import _ENGINE, _NODE_KINDS
from warframe_lore.kim_dm.traversal import (
    build_graph,
    build_messages,
    build_script,
)


def _node_kind(node: dict) -> str:
    """Role of the exact native type; unknown types stay as system nodes."""
    return _NODE_KINDS.get(node.get("type", ""), "system")


def _rank_from_id(conv_id: str) -> str:
    match = re.search(r"Rank\s*(\d+)", conv_id, re.I)
    return f"Rank {match.group(1)}" if match else ""


class _DialogueFile:
    """Parser of native nodes; no reconstruction from Incoming data."""

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

    def kind(self, node: dict) -> str:
        """Role of the exact native type (start/npc/choice/chemistry/system/end)."""
        return _node_kind(node)

    def _text_of(self, value: Any) -> str:
        """Resolve a dictionary key without altering the native text."""
        value = "" if value is None else str(value)
        return self.text.get(value, value)

    def _system_text(self, node: dict) -> str:
        """Describe actions and conditions without executing them."""
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
        """One edge per native entry, including parallel routes."""
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


def parse_dialogue_file(nodes: list[dict], text: dict[str, str],
                        sender: str = "") -> list[dict]:
    """Reconstruct the conversations of a ``[Char]Dialogue_rom.dialogue.json``.

    One conversation per exact native ``StartDialogueNode`` type. The graph
    contains all IDs reachable via native outgoing routes only.
    ``sender`` is the fallback wiki name for NPCs without an explicit Speaker.
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
            "graph": build_graph(parser, start),
            "messages": build_messages(parser, start),
            "script": build_script(parser, start),
        })
    conversations.sort(key=lambda c: c["id"])
    return conversations