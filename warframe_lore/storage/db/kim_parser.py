"""Extraction of KIM dialogues from cleaned Markdown.

The KIM pages (``Kinemantik Instant Messenger``) are rendered by the
cleaner as readable blockquotes:
    ``> **Amir:** Salut Tenno, t'as vu le nouveau graff ?``
    ``> **Arthur:** ...``

This module converts this rendering into structured rows for the
``kim_dialogues`` table (speaker + text + chronological order).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .kim_filter import is_dialogue_junk

# Bold format (cleaner output): '> **Amir:** text'.
# NB: the colon is INSIDE the bold (``**Amir:**`` = ``**`` + ``Amir:`` + ``**``).
_KIM_BOLD_LINE_PATTERN = re.compile(
    r"^>\s*\*\*(?P<line>[^*]+?)\*\*\s*(?P<text>.*)$"
)
# Plain format: '> Amir : text' (fallback).
_KIM_PLAIN_LINE_PATTERN = re.compile(
    r"^>\s*(?P<speaker>[^:]+?)\s*:\s*(?P<text>.*)$"
)
# KIM branch option (player choice): '> > choice text'.
_KIM_CHOICE_LINE_PATTERN = re.compile(r"^>\s*>\s*(?P<text>.+)$")


@dataclass(frozen=True)
class KimMessage:
    """A structured message extracted from a KIM conversation."""

    message_order: int
    speaker: str
    message_text: str
    timestamp: str | None = None
    player_choice: bool = False


def extract_kim_messages(markdown_text: str) -> list[KimMessage]:
    """Extracts structured KIM messages from cleaned Markdown.

    Returns ``[]`` if the text contains no dialogue line in the expected
    format.  The returned order matches the order of appearance.
    """
    messages: list[KimMessage] = []
    for line in markdown_text.split("\n"):
        stripped_line = line.strip()
        match = _KIM_BOLD_LINE_PATTERN.match(stripped_line)
        if match is not None:
            bolded_segment = match.group("line")
            speaker_name, _, _ = bolded_segment.rpartition(":")
            speaker_name = speaker_name.strip()
            message_text = match.group("text").strip()
            player_choice = False
        else:
            # ``> > option``: branch choice = player input (KIM).
            choice = _KIM_CHOICE_LINE_PATTERN.match(stripped_line)
            if choice is not None:
                choice_text = choice.group("text").strip()
                if choice_text and not is_dialogue_junk("", choice_text):
                    messages.append(KimMessage(
                        message_order=len(messages),
                        speaker="",
                        message_text=choice_text,
                        timestamp=None,
                        player_choice=True,
                    ))
                continue
            match = _KIM_PLAIN_LINE_PATTERN.match(stripped_line)
            if match is None:
                continue
            speaker_name = match.group("speaker").strip()
            message_text = match.group("text").strip()
            player_choice = False
        if not speaker_name or not message_text:
            continue
        # Filters out cleaner artifacts (spoiler blockquotes, etc.): a real
        # speaker name contains neither '*' nor '_' nor tags.
        if not _looks_like_speaker_name(speaker_name):
            continue
        # Business exclusion: UI labels, patch-note phrases, loot/drop
        # mechanics and bare numeric values never enter the table.
        if is_dialogue_junk(speaker_name, message_text):
            continue
        messages.append(KimMessage(
            message_order=len(messages),
            speaker=speaker_name,
            message_text=message_text,
            timestamp=None,
            player_choice=player_choice,
        ))
    return messages


def _looks_like_speaker_name(candidate: str) -> bool:
    """True if the 'speaker' looks like a plausible KIM character.

    Excludes formatting artifacts (``*_SPOILERS_* _``, ``**[...]``) that
    have no proper name, and whole sentences pushed into the leading bold
    segment ("Banishing an Eximus enemy will remove its Aura ..., eg:").
    """
    if any(marker in candidate for marker in ("*", "_", "]", "}", ":")):
        return False
    if len(candidate) > 40:
        return False
    return candidate[0].isalpha() and candidate[0].isupper()
