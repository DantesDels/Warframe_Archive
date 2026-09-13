"""Wiki dialogue recognition, extraction & conversation splitting.

Single responsibility: recognise dialogue lines from WARFRAME wiki pages
(KIM and quests) — extraction, cleanup of navigation instructions, spoiler
warnings and section splitting by conversations.  Reference normalisation
machinery lives in :mod:`warframe_lore.ui.dialogue.refs`.
"""

from __future__ import annotations

import re

from ..patch_notes import split_lines
from .refs import (
    _DIALOGUE_STRIP_CHARS,
    clean_kim_text,
    is_player_speaker,
    slug_for_id,
)

KIM_BUCKET_ID = "Lore_Dialogues_KIM"

_BLOCKQUOTE_SPEAKER = re.compile(r"^>\s*\*\*(?P<speaker>[^*:]+):\*\*\s*(?P<text>.*)$")

# KIM page header boilerplate (to exclude from dialogues).
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

# Spoiler warning: ``> *_SPOILERS_* _: <reason>_``
_SPOILER_WARNING = re.compile(
    r"^>?\s*\*_SPOILERS_\*\s*_?:\s*(?P<reason>.+?)_?\s*$", re.I)

# KIM navigation instruction at the head of a dialogue line (wiki pointers):
#   ``> **{Continues as above from "X:** ..."`` | ``> **{Same as below:}**``
#   | ``> **{Jump above to "X:** ..."`` | ``> **{Continue with convo below:}**``
#   | ``> **{Goes the same as above, from:}**``
# and variants prefixed by one or more conditions
# ``> **{If ...} {If ...} {Continues ...}`` or ``> **> {...`` / ``> > {...``.
# The navigation keyword ALWAYS lives inside braces: never in the text of
# an ordinary line.  Closing brace is not required.
_KIM_POINTER_LINE = re.compile(
    r"(?im)^>[ \t]*(?:\*{1,3}[ \t]*)?(?:>[ \t]*)?(?:"
    r"\{[^{}:\n]*?(?:continues?|contiue|same|goes|jump)[^{}:\n]*"
    r"|(?:\{[^{}:\n]*?\}\s*)+?\{[^{}:\n]*?(?:continues?|contiue|same|goes|jump)[^{}:\n]*"
    r")")

# Strict blacklist: page footer noise lines (wiki navboxes) that a
# ``> …`` or a speaker should never turn into a dialogue line.
_DIALOGUE_EXCLUDE_EXACT = {"quotesnav", "quotes", "sentient"}
_DIALOGUE_EXCLUDE_RE = re.compile(r"^\s*update\s*\d+.*$", re.I)


# Section titles that delimit a KIM conversation (``###``/``####`` …):
#   ``### Conversation 1 (Tell me about yourself / ...)``
_KIM_SECTION_TITLE = re.compile(r"^#{3,}\s*(?P<title>.+?)\s*$")
# Rank header that precedes conversations: ``## Rank 1 - Neutral``
_KIM_RANK_TITLE = re.compile(
    r"^#{1,3}\s+Rank\s+(?P<n>\d+)\s*[-–—:]\s*(?P<label>.+)$", re.I)
# Conversation number within its title: ``Conversation 3 (...)``.
_KIM_CONVO_NUMBER = re.compile(r"^Conversation\s+(\d+)\b", re.I)


def speakers(content: str) -> list[str]:
    """Speakers of the dialogue page, in order of appearance."""
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
    """Linear message list ``[{index, speaker, text, player, lines}]`` from a page.

    ``lines`` is the text split into lines (one entry per line) for
    spaced chat display.  Boilerplate and KIM pointer lines are ignored.
    """
    messages: list[dict] = []
    for index, line in enumerate(content.splitlines(), start=1):
        stripped = line.strip()
        if _BOILERPLATE_LINE.match(stripped) or _KIM_POINTER_LINE.match(line):
            continue
        # Strict exclusion filter: page footer noise (``quotesnav``,
        # ``Quotes``, ``Sentient``) and ``Update N`` history.
        if (stripped.casefold() in _DIALOGUE_EXCLUDE_EXACT
                or _DIALOGUE_EXCLUDE_RE.match(stripped)):
            continue
        match = _BLOCKQUOTE_SPEAKER.match(stripped)
        if match:
            speaker = clean_kim_text(match.group("speaker").strip())
            text = clean_kim_text(match.group("text").strip())
            text = text.strip(_DIALOGUE_STRIP_CHARS)
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
                text = text.strip(_DIALOGUE_STRIP_CHARS)
                messages.append({
                    "index": index,
                    "speaker": "",
                    "text": text,
                    "player": True,
                    "lines": split_lines(text),
                })
            elif stripped.startswith("> "):
                text = clean_kim_text(stripped[2:].strip())
                text = text.strip(_DIALOGUE_STRIP_CHARS)
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
    """Spoiler warning reason from a KIM page, if present.

    KIM pages start with ``> *_SPOILERS_* _: <reason or Spoiler>_``.
    Returns the reason (or "Spoiler" by default), otherwise ``None``.
    """
    for line in content.splitlines():
        m = _SPOILER_WARNING.match(line.strip())
        if m:
            reason = m.group("reason").strip().strip("_")
            return reason or "Spoiler"
    return None


def looks_like_dialogue(content: str) -> bool:
    """True if the content looks like a dialogue transcription."""
    return any(line.strip().startswith("> **")
               for line in content.splitlines()[:200])


def make_snippet(content: str, query: str, radius: int = 60) -> str:
    """Extract a cleaned snippet around the hit."""
    needle = query.casefold()
    position = content.casefold().find(needle)
    if position < 0:
        text = content[:2 * radius].strip()
    else:
        text = content[max(0, position - radius):position + radius].strip()
    # Wiki artifact cleanup
    text = re.sub(r"\|[-|]+\|?\s*", " ", text)      # |-|, ||, |||, |-
    text = re.sub(r"\{[^}]+\}", " ", text)           # {if...}, {Convo ends.}
    text = re.sub(r"_[^_]+_?", " ", text)            # _italic_
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)  # **bold**
    text = re.sub(r"==[^=]+==", " ", text)           # ==highlight==
    text = re.sub(r"~{2}[^~]+~{2}", " ", text)      # ~~strike~~
    text = re.sub(r"\[[^\]]*\]", " ", text)          # [links / refs]
    text = re.sub(r"[|]", " ", text)                 # residual pipes
    text = re.sub(r"\s+", " ", text).strip()
    prefix = "…" if position > radius else ""
    suffix = "…" if 0 <= position < len(content) - radius else ""
    return prefix + text + suffix


def split_kim_conversations(page_title: str, content: str) -> list[dict]:
    """Split a KIM page into distinct conversations.

    Each conversation is delimited by a ``### …`` section title
    (Wiki = ``=== … ===``), typically ``### Conversation 1 (topic)``,
    optionally under a ``## Rank N - X`` header.  Like ``browse.wf``,
    this yields independent dialogue branches.

    Returns:
        Ordered list of dicts ``{id, title, rank, body}`` where ``body`` is
        the Markdown of the conversation (section title included: the
        ``build_dialogue_graph``/``parse_dialogue`` parsers use it to
        skip the preamble).
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

    # Guarantee uniqueness of ids (repeated titles/numbering).
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
