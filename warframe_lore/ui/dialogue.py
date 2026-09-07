"""Parsing des dialogues wiki (blocquotes ``> **Locuteur:** texte``).

Responsabilité unique : reconnaître et normaliser les répliques des pages de
dialogue du wiki WARFRAME (KIM et quêtes) — extraction, dépollution des
instructions d'enchaînement, découpage des conversations par sections.
"""

from __future__ import annotations

import re

from .patch_notes import split_lines

KIM_BUCKET_ID = "Lore_Dialogues_KIM"

_BLOCKQUOTE_SPEAKER = re.compile(r"^>\s*\*\*(?P<speaker>[^*:]+):\*\*\s*(?P<text>.*)$")

# Boilerplate d'en-tête des pages KIM (à exclure des dialogues).
_BOILERPLATE_LINE = re.compile(
    r"^>?\s*(\*_SPOILERS_\*|_?:|_ |Notes:|All ending conversations|"
    r"A flow chart will be included|"
    r"The corresponding flow chart|Any glowing, golden text|"
    r"Indented messages|All user input is marked|All user's choices|"
    r"Rank [0-9]|Alty|_SPOILERS_|"
    r"[\(\{\[\[]?\s*(line|lines)\s+(required|needed|reqquired)|"
    r"[\(\{\[\[]?\s*(same as (the )?below|same\s*-?\s*as\s+-?\s*above|"
    r"goes the same as below choice|jump to above branch|"
    r"jump to \"|choices same as|"
    r"to next set of choices|end of conversation|continues as above|"
    r"continues above)|"
    r"^>?\s*[^A-Za-z0-9]{0,3}\s*DFF\w+\.ogg|-\s*[A-Z]?\.?\s*Lyon\b)", re.I)

# Avertissement spoiler : ``> *_SPOILERS_* _: <raison>_``
_SPOILER_WARNING = re.compile(
    r"^>?\s*\*_SPOILERS_\*\s*_?:\s*(?P<reason>.+?)_?\s*$", re.I)

# Instruction de navigation KIM en tête de ligne de dialogue (pointeurs wiki) :
#   ``> **{Continues as above from "X:** ..."`` | ``> **{Same as below:}**``
#   | ``> **{Jump above to "X:** ..."`` | ``> **{Continue with convo below:}**``
#   | ``> **{Goes the same as above, from:}**``
# et les variantes préfixées par une ou plusieurs conditions
# ``> **{If ...} {If ...} {Continues ...}`` ou ``> **> {...`` / ``> > {...``.
# Le mot-clé de navigation vit TOUJOURS dans une accolade : jamais dans le
# texte d'une réplique ordinaire.  La fermeture de l'accolade n'est pas exigée.
_KIM_POINTER_LINE = re.compile(
    r"(?im)^>[ \t]*(?:\*{1,3}[ \t]*)?(?:>[ \t]*)?(?:"
    r"\{[^{}:\n]*?(?:continues?|contiue|same|goes|jump)[^{}:\n]*"
    r"|(?:\{[^{}:\n]*?\}\s*)+?\{[^{}:\n]*?(?:continues?|contiue|same|goes|jump)[^{}:\n]*"
    r")")
# Pointeur de navigation embarqué au milieu d'un message (fermé) : ``{...}``
# contenant un mot-clé de navigation -> retiré du texte du message.  Exige la
# fermeture de l'accolade pour ne jamais tronquer la réplique, et exclut les
# marqueurs terminaux ``{... ends ...}`` (ex: ``{Convo. Ends. Followed by
# jumpscare image.}``) qui pourraient contenir ``jump`` ou ``same``.
_KIM_INLINE_NAV = re.compile(
    r"\{(?!.*\bends\b)[^{}\n]*?(?:continues?|contiue|same|goes|jump)[^{}\n]*\}", re.I)
# Conditions de branche (``{If ...}``) et marqueurs de position (``{P1}``…) :
# purgés du texte des messages (locuteur/parole).
_KIM_CONDITION_MARK = re.compile(r"\{\s*if\s+[^{}]*\}", re.I)
_KIM_POSITION_MARK = re.compile(r"\{P\d+\}", re.I)

# Titres de section qui délimitent une conversation KIM (``###``/``####`` …) :
#   ``### Conversation 1 (Tell me about yourself / ...)``
_KIM_SECTION_TITLE = re.compile(r"^#{3,}\s*(?P<title>.+?)\s*$")
# En-tête de rang qui précède les conversations : ``## Rank 1 - Neutral``
_KIM_RANK_TITLE = re.compile(
    r"^#{1,3}\s+Rank\s+(?P<n>\d+)\s*[-–—:]\s*(?P<label>.+)$", re.I)
# Numéro d'une conversation dans son titre : ``Conversation 3 (...)``.
_KIM_CONVO_NUMBER = re.compile(r"^Conversation\s+(\d+)\b", re.I)

# Marqueur terminal d'une conversation KIM (``{Convo ends.}`` et variantes).
_CONVO_ENDS = re.compile(r"\{[Cc]onvo[^}\n]{0,16}ends\.?\}", re.I)
_JUMP_ABOVE = re.compile(
    r"\[(?:Continues|Same) as above[,:]?\s*from:?\s*\"(?P<ref>[^\"]*)\",?\s*\]", re.I)
_JUMP_BELOW = re.compile(r"\[Goes the same as below choice\]", re.I)
_ANNOT_PAREN = re.compile(r"^\(\s*(?P<body>.*)\s*\)$", re.S)
_ANNOT_BRACKET = re.compile(r"^\[\s*(?P<body>.*)\s*\]$", re.S)
_JUMP_QUOTED = re.compile(
    r"conversation\s+continues\s+as\s+below[,:]?\s+starting\s+at\s+"
    r"\"(?P<below>[^\"]*)\""
    r"|\bsame\s+as\s+above[,:]?\s+from:?\s+\"(?P<above>[^\"]*)\"",
    re.I)
_JUMP_VAGUE = re.compile(
    r"\[goes\s+(?:the\s+)?same\s+as\s+(?:above|below(?:\s+choice)?|choice)\]",
    re.I)


def clean_kim_text(text: str) -> str:
    """Retire les instructions d'enchaînement KIM d'un texte.

    Purge les conditions de branche (``{If ...}``), marqueurs de position
    (``{P1}`` … ``{P5}``) et pointeurs de navigation fermés (``{Continues
    ...}``, ``{Same ...}``, ``{Jump ...}``, ``{Goes ...}``) embarqués dans
    le message.  Les didascalies (``{Smile!}``, …) et ``{Convo. ends.}``
    (terminal) sont conservées.
    """
    cleaned = _KIM_INLINE_NAV.sub("", text or "")
    cleaned = _KIM_CONDITION_MARK.sub("", cleaned)
    cleaned = _KIM_POSITION_MARK.sub("", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def is_player_speaker(speaker: str) -> bool:
    """Vrai si le locuteur est le personnage du joueur (Tenno)."""
    return bool(re.search(
        r"operator|player|\btenno\b|drifter|walley|indifference", speaker, re.I))


def speakers(content: str) -> list[str]:
    """Locuteurs de la page de dialogue, dans l'ordre d'apparition."""
    result: list[str] = []
    for line in content.splitlines():
        if _KIM_POINTER_LINE.match(line):
            continue
        match = _BLOCKQUOTE_SPEAKER.match(line.strip())
        if match:
            name = clean_kim_text(match.group("speaker").strip())
            if name and name not in result:
                result.append(name)
    return result


def parse_dialogue(content: str) -> list[dict]:
    """Message linéaire ``[{index, speaker, text, player, lines}]`` d'une page.

    ``lines`` est le texte découpé en répliques (une entrée par ligne) pour
    l'affichage aéré du chat.  Les lignes boilerplate et pointeurs KIM sont
    ignorés.
    """
    messages: list[dict] = []
    for index, line in enumerate(content.splitlines(), start=1):
        stripped = line.strip()
        if _BOILERPLATE_LINE.match(stripped) or _KIM_POINTER_LINE.match(line):
            continue
        match = _BLOCKQUOTE_SPEAKER.match(stripped)
        if match:
            speaker = clean_kim_text(match.group("speaker").strip())
            text = clean_kim_text(match.group("text").strip())
            messages.append({
                "index": index,
                "speaker": speaker,
                "text": text,
                "player": is_player_speaker(speaker),
                "lines": split_lines(text),
            })
        else:
            nested = re.match(r"^>\s*>\s*(?P<text>.+)$", stripped)
            if nested:
                text = clean_kim_text(nested.group("text").strip())
                messages.append({
                    "index": index,
                    "speaker": "",
                    "text": text,
                    "player": True,
                    "lines": split_lines(text),
                })
            elif stripped.startswith("> "):
                text = clean_kim_text(stripped[2:].strip())
                if text:
                    messages.append({
                        "index": index,
                        "speaker": "",
                        "text": text,
                        "player": False,
                        "lines": split_lines(text),
                    })
    return messages


def spoiler_warning(content: str) -> str | None:
    """Raison d'avertissement spoiler d'une page KIM, si présente.

    Les pages KIM débutent par ``> *_SPOILERS_* _: <raison or Spoiler>_``.
    Retourne la raison (ou "Spoiler" par défaut), sinon ``None``.
    """
    for line in content.splitlines():
        m = _SPOILER_WARNING.match(line.strip())
        if m:
            reason = m.group("reason").strip().strip("_")
            return reason or "Spoiler"
    return None


def looks_like_dialogue(content: str) -> bool:
    """Vrai si le contenu semble être une transcription de dialogue."""
    return any(line.strip().startswith("> **")
               for line in content.splitlines()[:200])


def normalise_dialogue_ref(text: str) -> str:
    """Forme canonique d'une réplique pour résoudre les références de saut."""
    t = text.casefold()
    t = re.sub(r"\{p\s*\d+\}", " ", t)          # {P1}/{P2} : pauses de page
    t = re.sub(r"\{[^{}]*\}", " ", t)           # {…} (conditions, {Convo ends.})
    t = re.sub(r"^>+\s*", "", t)                # "> Ah" -> "Ah"
    t = re.sub(r"[.!?]+$", "", t)               # ponctuation finale
    t = re.sub(r"\s+", " ", t).strip()
    return t


def normalise_ref(text: str) -> str:
    """Normalise une chaîne pour la résolution des renvois (sauts)."""
    out = _CONVO_ENDS.sub("", text)
    out = re.sub(r"\s+", " ", out).strip().strip("*").strip()
    return out.lower()[:120]


def slug_for_id(text: str) -> str:
    """Chaîne identifiant ASCII simple (alphabétique) depuis un texte."""
    return re.sub(r"[^A-Za-z0-9]+", "", text)


def make_snippet(content: str, query: str, radius: int = 60) -> str:
    """Extrait un extrait nettoyé autour du hit."""
    needle = query.casefold()
    position = content.casefold().find(needle)
    if position < 0:
        text = content[:2 * radius].strip()
    else:
        text = content[max(0, position - radius):position + radius].strip()
    # Nettoyage artefacts wiki
    text = re.sub(r"\|[-|]+\|?\s*", " ", text)      # |-|, ||, |||, |-
    text = re.sub(r"\{[^}]+\}", " ", text)           # {if...}, {Convo ends.}
    text = re.sub(r"_[^_]+_?", " ", text)            # _italique_
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)  # **bold**
    text = re.sub(r"==[^=]+==", " ", text)           # ==highlight==
    text = re.sub(r"~{2}[^~]+~{2}", " ", text)      # ~~strike~~
    text = re.sub(r"\[[^\]]*\]", " ", text)          # [links / refs]
    text = re.sub(r"[|]", " ", text)                 # pipes résiduels
    text = re.sub(r"\s+", " ", text).strip()
    prefix = "…" if position > radius else ""
    suffix = "…" if 0 <= position < len(content) - radius else ""
    return prefix + text + suffix


def split_kim_conversations(page_title: str, content: str) -> list[dict]:
    """Découpe une page KIM en conversations distinctes.

    Chaque conversation est délimitée par un titre de section ``### …``
    (Wiki = ``=== … ===``), typiquement ``### Conversation 1 (sujet)``,
    éventuellement sous un en-tête de rang ``## Rank N - X``.  À l'instar de
    ``browse.wf``, on obtient ainsi des branches de dialogue indépendantes.

    Returns:
        Liste ordonnée de dicts ``{id, title, rank, body}`` où ``body`` est
        le Markdown de la conversation (titre de section inclus : les parseurs
        ``build_dialogue_graph``/``parse_dialogue`` s'en servent pour franchir
        leur préambule).
    """
    character = page_title.rsplit("/", 1)[-1].strip()
    head = slug_for_id(character)
    lines = content.splitlines()

    segments: list[dict] = []
    pending: dict | None = None
    pending_start = 0
    rank_n: str = ""
    rank_display: str = ""

    def flush(end: int) -> None:
        nonlocal pending, pending_start
        if pending is None:
            return
        pending["body"] = "\n".join(lines[pending_start:end]).rstrip()
        segments.append(pending)
        pending = None
        pending_start = end

    for index, line in enumerate(lines):
        stripped = line.strip()
        rank_match = _KIM_RANK_TITLE.match(stripped)
        if rank_match:
            flush(index)
            rank_n = rank_match.group("n")
            rank_display = (f"Rank {rank_n} - "
                            f"{rank_match.group('label').strip()}")
            continue
        section_match = _KIM_SECTION_TITLE.match(stripped)
        if section_match:
            flush(index)
            section_title = section_match.group("title").strip()
            base_id = f"{head}Rank{rank_n}" if rank_n else head
            convo = _KIM_CONVO_NUMBER.match(section_title)
            if convo:
                base_id += f"Convo{convo.group(1)}"
            else:
                base_id += slug_for_id(section_title)
            pending = {
                "id": base_id,
                "title": section_title,
                "rank": rank_display,
            }
            pending_start = index
    flush(len(lines))

    # Garantit l'unicité des identifiants (titres/numérotations répétés).
    seen: set[str] = set()
    for segment in segments:
        base = segment["id"]
        if base in seen:
            suffix = 2
            while f"{base}-{suffix}" in seen:
                suffix += 1
            segment["id"] = f"{base}-{suffix}"
        seen.add(segment["id"])
    return segments