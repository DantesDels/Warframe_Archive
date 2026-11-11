"""Structured dialogue extraction (KIM, cinematic transcripts, voice quotes).

Reuses the KIM line patterns and the junk filter of ``db.kim_parser`` and
adds the fields the ``game_dialogues`` table needs for human reading: a
parent tag (quest / character, supplied by the caller), the ``##`` chapter
heading, and the KIM chemistry gain marker (``{Convo ends.}``) promoted to
a boolean flag instead of leaking wiki markup.

``extract_kim_messages`` (db.kim_parser) cannot carry chapter and chemistry
without an API change, so this module walks the lines itself but shares the
exact same line patterns and speaker heuristic (DRY).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..db.kim_filter import is_dialogue_junk
from ..db.kim_parser import (
    _KIM_BOLD_LINE_PATTERN,
    _KIM_CHOICE_LINE_PATTERN,
    _KIM_PLAIN_LINE_PATTERN,
    _looks_like_speaker_name,
)

_HEADING_PATTERN = re.compile(r"^##\s+(?P<chapter>.+)$")
# KIM glowing marker: an invisible in-game chemistry gain at the end of a
# conversation branch.  Promoted to its own boolean column.
# Covers all bracket variants seen in the wiki: {…}, (…) and […].
_CHEMISTRY_PATTERN = re.compile(
    r"[\[{(]\s*convo[\s.]+ends?\.?\s*[\s.)\]\}]", re.IGNORECASE
)


@dataclass(frozen=True)
class DialogueLine:
    """A structured dialogue line ready to insert into ``game_dialogues``."""

    message_order: int
    speaker: str
    message_text: str
    player_choice: bool = False
    chemistry_gain: bool = False
    chapter: str | None = None


def parse_dialogues(
    kind: str, context: str | None, markdown: str
) -> list[DialogueLine]:
    """Parses one dialogue page into ordered ``DialogueLine`` rows.

    ``kind`` is ``kim``, ``cinematic`` or ``quote``; ``context`` is the
    parent tag stored as-is (quest or character).  KIM pages open with
    legend blockquotes (``> *_SPOILERS_*``, ``> All ending conversations
    ...``) that are page documentation, not dialogue: everything before
    the first ``##`` heading is ignored.
    """
    messages: list[DialogueLine] = []
    chapter: str | None = None
    past_intro = kind != "kim"
    for raw_line in markdown.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        heading = _HEADING_PATTERN.match(line)
        if heading is not None:
            chapter = heading.group("chapter").strip()
            past_intro = True
            continue
        if not past_intro:
            continue
        parsed = _match_message(line)
        if parsed is None:
            # Standalone chemistry marker ('> {Convo ends.}'): it closes the
            # previous branch, so the gain lands on the preceding line.
            if messages and _CHEMISTRY_PATTERN.search(line):
                previous = messages[-1]
                messages[-1] = DialogueLine(
                    message_order=previous.message_order,
                    speaker=previous.speaker,
                    message_text=previous.message_text,
                    player_choice=previous.player_choice,
                    chemistry_gain=True,
                    chapter=previous.chapter,
                )
            continue
        speaker, text, player_choice = parsed
        gain_match = _CHEMISTRY_PATTERN.search(text)
        if gain_match is not None:
            text = _CHEMISTRY_PATTERN.sub("", text).strip()
        if player_choice:
            if text and not is_dialogue_junk("", text):
                messages.append(
                    DialogueLine(
                        message_order=len(messages),
                        speaker="",
                        message_text=text,
                        player_choice=True,
                        chemistry_gain=gain_match is not None,
                        chapter=chapter,
                    )
                )
            continue
        if (
            speaker
            and text
            and _looks_like_speaker_name(speaker)
            and not is_dialogue_junk(speaker, text)
        ):
            messages.append(
                DialogueLine(
                    message_order=len(messages),
                    speaker=speaker,
                    message_text=text,
                    player_choice=False,
                    chemistry_gain=gain_match is not None,
                    chapter=chapter,
                )
            )
    return messages


def _match_message(line: str) -> tuple[str, str, bool] | None:
    """Maps a dialogue line to ``(speaker, text, is_player_choice)``.

    Same accepting formats as ``db.kim_parser``: bold lines
    (``> **Amir:** text``), player choices (``> > option``) and the plain
    fallback (``> Amir : text``).  Returns ``None`` for anything else
    (notes, images, table rows).
    """
    match = _KIM_BOLD_LINE_PATTERN.match(line)
    if match is not None:
        bolded = match.group("line")
        speaker_name, _, _ = bolded.rpartition(":")
        return speaker_name.strip(), match.group("text").strip(), False
    choice = _KIM_CHOICE_LINE_PATTERN.match(line)
    if choice is not None:
        return "", choice.group("text").strip(), True
    match = _KIM_PLAIN_LINE_PATTERN.match(line)
    if match is None:
        return None
    return match.group("speaker").strip(), match.group("text").strip(), False


__all__ = ["DialogueLine", "parse_dialogues"]
