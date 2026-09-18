"""Storyteller: detection and starting-point (lens) of a narrative request.

Pure module (no discord.py, no I/O): decides when a request opens a story and
which of the three canonical lenses it starts from — the Tenno awakening
``initiate``, the origin of the universe ``cosmogonic`` or the 1999 experiment
``1999``.  An ambiguous request returns ``None``: the bot then ASKS the user
before opening the story, instead of guessing a wrong starting point.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Canonical era mapping for targeted narrative requests (generated from the
# archive database: wiki_pages, kim_dialogues, game_dialogues, warframes,
# game_quests).  Keys are lowercase substrings; values are era labels injected
# into the targeted-story directive.
from .story_eras import LEVERIAN_WARFRAMES, TARGETED_SUBJECT_ERAS

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

# Corrective reply when the author answers an INDEX OUT OF the open menu
# (e.g. "4" to a 1..3 question): the bot points out the mistake and keeps the
# question open, instead of silently re-printing the same menu.
MENU_INDEX_ERROR = (
    "Hors de mon répertoire, organique : ce numéro n'existe pas. "
    "Réponds-moi par un chiffre entre 1 et {}."
)

# Named subjects whose history is ambiguous: one word, TWO distinct tales in
# the archives.  A story request naming one must ask WHICH tale the user wants
# (never guess).  Keys are the mention keywords (lowercase, substring match),
# values the candidate subjects offered in the question.
STORY_SUBJECT_CHOICES = {
    "garuda": ("Vena", "l'archimédienne"),
}

SUBJECT_QUESTION_INTRO = (
    "Le récit que tu demandes a plusieurs visages dans les archives, "
    "organique. Lequel veux-tu entendre ? Réponds-moi par un chiffre :\n")
SUBJECT_QUESTION_OUTRO = "Ou pardonne ma prudence : je t'écoute."


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


def detect_targeted_era(text: str) -> str | None:
    """Canonical era of a specifically named subject, or ``None``.

    When a story request names one of these subjects, the bot must skip the
    lens menu and anchor the narrative directly in that subject's era.
    """
    low = (text or "").lower()
    for mention, era in TARGETED_SUBJECT_ERAS.items():
        if mention in low:
            return era
    return None


def targeted_subject_mention(text: str) -> str | None:
    """Matched subject KEY of a targeted story request, or ``None``.

    Same first-match scan as :func:`detect_targeted_era` but returns the
    mention itself (``"eleanor"``, ``"the hex"``…) instead of the era label:
    the ENGRAM dossier retrieval anchors the story corpus on the wiki pages
    whose title contains this very key.
    """
    low = (text or "").lower()
    for mention in TARGETED_SUBJECT_ERAS:
        if mention in low:
            return mention
    return None


def detect_leverian_warframe(text: str) -> str | None:
    """Name of a Warframe whose story is told by Drusus in the Leverian.

    Returns the matched lowercase frame name, or ``None`` if the request does
    not name one of the Leverian Warframes.
    """
    low = (text or "").lower()
    for frame in LEVERIAN_WARFRAMES:
        if frame in low:
            return frame
    return None


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


def is_out_of_range_index(text: str, count: int) -> bool:
    """True when the answer is a plain integer OUTSIDE the menu (1..count).

    Distinguishes a menu mistake ("4" to a 1..3 question) from any other
    invalid answer: the bot then points out the index error to the author.
    """
    low = (text or "").strip()
    if not low.isdigit():
        return False
    return not 1 <= int(low) <= count


def story_subject(text: str) -> str | None:
    """Ambiguous-subject mention of a story request (``None`` if none)."""
    low = (text or "").lower()
    for mention in STORY_SUBJECT_CHOICES:
        if mention in low:
            return mention
    return None


def story_subject_choices(text: str) -> tuple[str, ...]:
    """Candidate tales of the named subject (``()`` when unambiguous)."""
    mention = story_subject(text)
    return STORY_SUBJECT_CHOICES.get(mention, ())


def story_subject_question(choices: tuple[str, ...]) -> str:
    """Ask WHICH tale the user wants among the subject's candidates."""
    lines = (f"  {index} — {choice}\n"
             for index, choice in enumerate(choices, start=1))
    return SUBJECT_QUESTION_INTRO + "".join(lines) + SUBJECT_QUESTION_OUTRO


def parse_subject_answer(text: str,
                         choices: tuple[str, ...]) -> str | None:
    """Interpret a subject answer (menu number or the tale's words)."""
    low = (text or "").strip().lower()
    for index, choice in enumerate(choices, start=1):
        if low == str(index):
            return choice
    for choice in choices:
        if choice.lower() in low:
            return choice
    return None


def substitute_story_subject(request: str, subject: str) -> str:
    """``request`` retold with the subject that disambiguated its mention."""
    mention = story_subject(request)
    if mention is None:
        return request
    return re.sub(re.escape(mention), subject, request, count=1,
                  flags=re.IGNORECASE)


__all__ = ["LEVERIAN_WARFRAMES", "LENS_1999", "LENS_COSMOGONIC",
           "LENS_INITIATE", "LENS_KEYWORDS", "LENS_LABELS", "LENS_QUESTION",
           "MENU_INDEX_ERROR", "STORY_SUBJECT_CHOICES", "STORY_TRIGGERS",
           "TARGETED_SUBJECT_ERAS", "StoryAsk", "detect_leverian_warframe",
           "detect_story_lens", "detect_targeted_era",
           "is_out_of_range_index", "is_story_request", "parse_lens_answer",
           "parse_subject_answer", "story_subject", "story_subject_choices",
           "story_subject_question", "substitute_story_subject"]
