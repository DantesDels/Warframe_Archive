"""Storyteller: detection and starting-point (lens) of a narrative request.

Pure module (no discord.py, no I/O): decides when a request opens a story and
which of the three canonical lenses it starts from — the Tenno awakening
``initiate``, the origin of the universe ``cosmogonic`` or the 1999 experiment
``1999``.  An ambiguous request returns ``None``: the bot then ASKS the user
before opening the story, instead of guessing a wrong starting point.
"""

from __future__ import annotations

from dataclasses import dataclass

# Narrative triggers (FR/EN): "raconte-moi l'histoire de…" and friends.
# A lore QUESTION ("Quelle est l'histoire des Orokin ?") is NOT a story: the
# trigger word must carry the REQUEST (verbative "raconte") or a possessive
# "de" ("l'histoire de l'univers"), never a standalone "l'histoire".
STORY_TRIGGERS = (
    "raconte",
    "conte-moi", "conte moi",
    "récit", "épopée de", "légende de",
    "l'histoire de ", "une histoire de",
    "les origines de", "la genèse de",
    "tell me the story", "a story about", "the story of", "story of",
    "story about", "history of", "recount",
)

LENS_INITIATE = "initiate"
LENS_COSMOGONIC = "cosmogonic"
LENS_1999 = "1999"

LENS_LABELS = {
    LENS_INITIATE: "l'éveil du Tenno",
    LENS_COSMOGONIC: "l'origine de l'univers",
    LENS_1999: "l'année 1999 (Albrecht Entrati)",
}

# Starting-point keywords of each lens.  A request hitting several families (or
# none) stays ambiguous — the bot asks the user instead of guessing.
LENS_KEYWORDS = {
    LENS_INITIATE: ("tenno", "operator", "opérateur", "warframe", "éveil",
                    "awakening", "voyageur", "old war", "la vieille guerre"),
    LENS_COSMOGONIC: ("univers", "cosmogon", "genèse", "genesis", "origines",
                      "creation", "création", "void", "le début", "beginning",
                      "primordial", "le vide"),
    LENS_1999: ("1999", "albrecht", "entrati", "hex", "protocole", "protocol",
                "drifter"),
}

LENS_QUESTION = (
    "Par quelle porte veux-tu que j'ouvre ce récit, organique ? "
    "Réponds-moi par un chiffre :\n"
    f"  1 — {LENS_LABELS[LENS_INITIATE]}\n"
    f"  2 — {LENS_LABELS[LENS_COSMOGONIC]}\n"
    f"  3 — {LENS_LABELS[LENS_1999]}\n"
    "Ou pardonne ma prudence : je t'écoute."
)


@dataclass(frozen=True)
class StoryAsk:
    """One open starting-point question of the storyteller (per channel)."""

    author_id: int
    request: str


def is_story_request(text: str) -> bool:
    """True when the request opens a narrative (a story is expected)."""
    low = (text or "").lower()
    return any(trigger in low for trigger in STORY_TRIGGERS)


def detect_story_lens(text: str) -> str | None:
    """Lens of a story request, or ``None`` when ambiguous.

    Exactly ONE keyword family must match: several families (or none) mean the
    starting point is not safe to guess — the bot asks the user instead.
    """
    low = (text or "").lower()
    hits = [lens for lens, words in LENS_KEYWORDS.items()
            if any(word in low for word in words)]
    return hits[0] if len(hits) == 1 else None


def parse_lens_answer(text: str) -> str | None:
    """Interpret the answer to :data:`LENS_QUESTION` (menu number or words)."""
    low = (text or "").strip().lower()
    for number, lens in (("1", LENS_INITIATE), ("2", LENS_COSMOGONIC),
                         ("3", LENS_1999)):
        if low == number:
            return lens
    for lens, label in LENS_LABELS.items():
        if low == lens or low == label.lower():
            return lens
    return detect_story_lens(low)


__all__ = ["LENS_1999", "LENS_COSMOGONIC", "LENS_INITIATE",
           "LENS_KEYWORDS", "LENS_LABELS", "LENS_QUESTION", "STORY_TRIGGERS",
           "StoryAsk", "detect_story_lens", "is_story_request",
           "parse_lens_answer"]
