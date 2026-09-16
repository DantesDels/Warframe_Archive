"""Pure rules that regenerate the DB-derived static lists (``story_eras.py``).

This module owns the deterministic decisions behind ``cephalon update``:
which era a Warframe or KIM character belongs to, how the Leverian
sections are matched against the base Warframe directory, and the exact
rendering of ``warframe_lore/discord/guild/story_eras.py``.  No I/O and no
database here — the queries live in :mod:`warframe_lore.update.lists`.
"""

from __future__ import annotations

import re

# Era labels used by the storyteller (values of TARGETED_SUBJECT_ERAS).
ERA_1999 = "1999 (Höllvania)"
ERA_CORPUS = "l'Ère Corpus"
ERA_GRINEER = "l'Ère Grineer"
ERA_OROKIN = "l'Ère Orokin"
ERA_EVEIL = "l'Éveil du Tenno"
ERA_OLD_WAR = "la Vieille Guerre"
ERA_XX99 = "XX99"
ERA_OLD_PEACE = "l'Ancienne Paix"
ERA_NEW_WAR = "la Nouvelle Guerre"

# Stable rendering order (== the order of the groups in story_eras.py).
ERA_ORDER = (ERA_1999, ERA_XX99, ERA_CORPUS, ERA_GRINEER, ERA_OROKIN,
             ERA_EVEIL, ERA_NEW_WAR, ERA_OLD_PEACE, ERA_OLD_WAR)

# Quest names (lowercase) whose canonical era is curated: quests are the
# only DB source that cannot be classified automatically without guessing.
# A quest not listed here is simply not auto-mapped.
QUEST_ERAS: dict[str, str] = {
    # 1999 (Höllvania)
    "the hex": ERA_1999,
    # l'Ère Corpus
    "deadlock protocol": ERA_CORPUS,
    # l'Ère Orokin
    "chimera prologue": ERA_OROKIN,
    "erra": ERA_OROKIN,
    "heart of deimos": ERA_OROKIN,
    "the duviri paradox": ERA_OROKIN,
    "the maker": ERA_OROKIN,
    "whispers in the walls": ERA_OROKIN,
    # l'Éveil du Tenno
    "angels of the zariman": ERA_EVEIL,
    "apostasy prologue": ERA_EVEIL,
    "awakening": ERA_EVEIL,
    "jade shadows": ERA_EVEIL,
    "jade shadows: constellations": ERA_EVEIL,
    "natah": ERA_EVEIL,
    "once awake": ERA_EVEIL,
    "rising tide": ERA_EVEIL,
    "the archwing": ERA_EVEIL,
    "the lotus eaters": ERA_EVEIL,
    "the new war": ERA_NEW_WAR,
    "the sacrifice": ERA_EVEIL,
    "the second dream": ERA_EVEIL,
    "the war within": ERA_EVEIL,
    "vor's prize": ERA_EVEIL,
    # la Vieille Guerre
    "the old peace": ERA_OLD_PEACE,
}

# KIM contexts that are NOT a playable character (spin-off series).
_KIM_CONTEXT_STOP = frozenset(("fables",))

_SECTION_RE = re.compile(r"Section:\s*([^\n\-|]+)")
_WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]+")


def kim_subjects_from_contexts(contexts: list[str]) -> set[str]:
    """Playable KIM characters extracted from the dialogue contexts.

    ``"KIM � Amir"`` (the DB stores a broken en-dash) yields ``amir`` and
    ``"KIM � Minerva, Velimir"`` yields two subjects.  Non-character
    contexts (e.g. "KIM � Fables & Frontiers") are dropped: the curated
    mapping already owns the fables entries.
    """
    subjects: set[str] = set()
    for context in contexts:
        ctx = (context or "").strip()
        if not ctx.upper().startswith("KIM "):
            continue
        if any(stop in ctx.lower() for stop in _KIM_CONTEXT_STOP):
            continue
        for token in ctx[4:].split(","):
            subject = " ".join(_WORD_RE.findall(token)).strip().lower()
            if subject:
                subjects.add(subject)
    return subjects


def leverian_frames_from_chunks(chunks: list[str],
                                base_frames: list[str]) -> frozenset[str]:
    """Leverian Warframes: gallery sections crossed with the base directory.

    Each chunk of the "Leverian" page carries a ``Section: Name`` heading
    (or a fragment of it).  A frame is part of the Leverian when its base
    name appears among those sections.  Returns ``frozenset()`` when the
    page does not match any frame (callers then keep the curated list).
    """
    sections: set[str] = set()
    for chunk in chunks:
        for match in _SECTION_RE.finditer(chunk or ""):
            name = match.group(1).strip().lower()
            if name:
                sections.add(name)
    bases = {name.strip().lower() for name in base_frames if name}
    return frozenset(sorted(sections & bases))


def merge_sources(
    mapping: dict[str, str],
    leverian: frozenset[str],
    *,
    frames: list[str] = (),
    kim_subjects: set[str] = frozenset(),
    quest_titles: list[str] = (),
    leverian_frames: frozenset[str] = frozenset(),
    ambiguous: frozenset[str] = frozenset(),
) -> tuple[dict[str, str], frozenset[str]]:
    """Adds the fresh DB sources to the curated mapping (never removes).

    Warframes -> Éveil (except ambiguous subjects), KIM characters -> 1999,
    curated quest titles -> their era.  The Leverian set is replaced only
    when the page yields a non-empty extraction (no destructive clearing
    on a parsing failure).
    """
    merged = dict(mapping)
    for name in frames:
        key = (name or "").strip().lower()
        if key and key not in ambiguous:
            merged.setdefault(key, ERA_EVEIL)
    for subject in sorted(kim_subjects):
        if subject:
            merged.setdefault(subject, ERA_1999)
    for title in quest_titles:
        key = (title or "").strip().lower()
        era = QUEST_ERAS.get(key)
        if era:
            merged.setdefault(key, era)
    final_leverian = leverian_frames or frozenset(leverian)
    return merged, final_leverian


_HEADER = (
    '"""Canonical era mapping for targeted narrative requests.\n'
    "\n"
    "Generated from the archive database (wiki_pages, kim_dialogues,\n"
    "game_dialogues, warframes, game_quests).  Keys are lowercase substrings;\n"
    "values are free-form era labels injected into the targeted-story directive.\n"
    '"""\n'
    "\n"
    "from __future__ import annotations\n"
    "\n"
    "# Targeted subjects with a canonical era.  When a story request names one\n"
    "# of them, the bot skips the lens menu and anchors the answer in that era.\n"
    "TARGETED_SUBJECT_ERAS: dict[str, str] = {\n"
)

_FOOTER_OPEN = (
    "}\n"
    "\n"
    "# Warframes whose canonical story is told by Drusus in the Leverian.\n"
    "# When a story request names one of them, the answer must be anchored on\n"
    "# Drusus' narration in the Leverian gallery.\n"
    "LEVERIAN_WARFRAMES: frozenset[str] = frozenset((\n"
)

_FOOTER_CLOSE = "))\n"


def render_story_eras(mapping: dict[str, str],
                      leverian: frozenset[str]) -> str:
    """Renders ``story_eras.py`` with the exact current format.

    Groups follow :data:`ERA_ORDER`; unknown eras (safety net for a manual
    curation that introduced a new label) are appended after the known ones.
    """
    groups: dict[str, list[str]] = {}
    others: list[str] = []
    for key, era in mapping.items():
        if era in ERA_ORDER:
            groups.setdefault(era, []).append(key)
        else:
            others.append(key)
    lines = [_HEADER]
    for era in ERA_ORDER:
        keys = sorted(groups.get(era, ()))
        if not keys:
            continue
        lines.append(f"    # {era}\n")
        lines.extend(f'    "{key}": "{era}",\n' for key in keys)
    for key in sorted(others):
        lines.append(f'    "{key}": "{mapping[key]}",\n')
    lines.append(_FOOTER_OPEN)
    lines.extend(f'    "{frame}",\n' for frame in sorted(leverian))
    lines.append(_FOOTER_CLOSE)
    return "".join(lines)


__all__ = [
    "ERA_1999", "ERA_XX99", "ERA_CORPUS", "ERA_EVEIL", "ERA_GRINEER",
    "ERA_OLD_PEACE", "ERA_OLD_WAR", "ERA_NEW_WAR", "ERA_ORDER",
    "ERA_OROKIN", "QUEST_ERAS", "kim_subjects_from_contexts",
    "leverian_frames_from_chunks", "merge_sources", "render_story_eras",
]
