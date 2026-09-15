"""Script linéaire du simulateur de messagerie KIM.

Responsabilité unique : convertir le fil de répliques d'une conversation en
étapes ``{kind, speaker, text, player, options, ends, jump_to}`` en résolvant
les annotations de saut ``[Convo continues as below, starting at "X"]``.
"""

from __future__ import annotations

from .dialogue import (
    _ANNOT_PAREN,
    _CONVO_ENDS,
    _JUMP_QUOTED,
    _JUMP_VAGUE,
    normalise_dialogue_ref,
    parse_dialogue,
)


def build_kim_script(content: str) -> list[dict]:
    """Script destiné au simulateur de messagerie KIM.

    Marche linéaire sur le walkthrough, enrichie par les métadonnées du
    script d'origine :

        * ``{Convo ends.}``   -> étape terminale (``ends``).
        * lignes ``> > ...``  -> regroupées en étape ``prompt`` (choix).
        * annotations parenthésées ``(...)`` -> ignorées (doublons déjà
          présents dans le fil linéaire).
        * annotations ``[Conversation continues as below, starting at "X"]``
          / ``[Same as above from: "X"]`` -> ``jump_to`` résolue vers l'index
          d'étape cible (None si introuvable).

    Returns:
        Liste d'étapes ``{kind: "npc"|"prompt", speaker, text, player,
        options, ends, jump_to}``.
    """
    records = parse_dialogue(content)
    # Classification des messages (index d'origine pour résolution saut).
    classified: list[tuple[int, str, dict, dict | None]] = []
    for orig_index, rec in enumerate(records):
        stripped = rec["text"].strip()
        surface = stripped.strip("*")   # "**(same as ...)**" -> "(same ...)"
        ends = bool(_CONVO_ENDS.search(stripped))
        scrubbed = _CONVO_ENDS.sub("", stripped).strip()
        if _ANNOT_PAREN.fullmatch(surface):
            # "(Choices same as ...)", "(Goes same as ...)", "(line required...)"
            classified.append((orig_index, "note", rec, None))
        elif surface.startswith("[") and surface.endswith("]"):
            if _JUMP_VAGUE.search(surface):
                classified.append((orig_index, "note", rec, None))
            else:
                jump = _JUMP_QUOTED.search(surface)
                if jump:
                    ref = jump.group("below") or jump.group("above")
                    direction = "below" if jump.group("below") else "above"
                    classified.append(
                        (orig_index, "note", rec,
                         {"ref": ref, "dir": direction, "at": orig_index}))
                else:
                    # "[...]" non reconnu -> didascalie, conservée.
                    classified.append((orig_index, "npc",
                                       {**rec, "text": scrubbed, "ends": ends}, None))
        elif not scrubbed:
            # Ligne ``{Convo ends.}`` seule : marqueur de fin.
            classified.append((orig_index, "term", rec, None))
        else:
            kind = "choice" if (rec["player"] and not rec["speaker"]) else "npc"
            classified.append((orig_index, kind,
                               {**rec, "text": scrubbed, "ends": ends}, None))

    steps: list[dict] = []
    raw_to_step: list[int | None] = [None] * len(records)
    index = 0
    count = len(classified)
    while index < count:
        orig_index, kind, rec, meta = classified[index]
        if kind == "note":
            index += 1
            continue
        if kind == "term":
            if steps:
                steps[-1]["ends"] = True
            index += 1
            continue
        if kind == "choice":
            options = []
            while index < count and classified[index][1] == "choice":
                options.append({
                    "text": classified[index][2]["text"],
                    "ends": bool(classified[index][2].get("ends")),
                })
                raw_to_step[classified[index][0]] = len(steps)
                index += 1
            steps.append({"kind": "prompt", "options": options,
                          "ends": False, "jump_to": None})
            continue
        # kind == "npc"
        step: dict = {
            "kind": "npc",
            "speaker": rec["speaker"],
            "text": rec["text"],
            "player": bool(rec["player"]),
            "ends": bool(rec.get("ends")),
            "jump_to": None,
        }
        steps.append(step)
        raw_to_step[orig_index] = len(steps) - 1
        index += 1

    # Résolution des sauts : la cible est référencée par texte normalisé.
    norm_to_origin: dict[str, list[int]] = {}
    for orig_index, rec in enumerate(records):
        key = normalise_dialogue_ref(rec["text"])
        if key:
            norm_to_origin.setdefault(key, []).append(orig_index)
    # L'annotation (posée après une réplique) pilote l'étape précédente :
    # ``anchor_step`` = dernière étape créée avant l'annotation.
    anchor_step: int | None = None
    for orig_index, kind, _rec, meta in classified:
        if kind == "term":
            continue
        if kind == "note":
            if meta is None or anchor_step is None:
                continue
            key = normalise_dialogue_ref(meta["ref"])
            origins = norm_to_origin.get(key) or []
            if meta["dir"] == "below":
                chosen = next((o for o in origins if o > meta["at"]), None)
            else:
                chosen = origins[0] if origins else None
            target = raw_to_step[chosen] if chosen is not None else None
            if (target is not None and target != anchor_step
                    and steps[anchor_step]["kind"] == "npc"):
                steps[anchor_step]["jump_to"] = target
        else:
            anchor_step = raw_to_step[orig_index]
    return steps
