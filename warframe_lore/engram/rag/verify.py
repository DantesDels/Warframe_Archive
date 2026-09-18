"""Deterministic post-generation confabulation gate.

Prompt-level guard rails (``HALLUCINATION_GUARD``, ``STORY_DIRECTIVE`` …)
depend on model obedience, which fails: the model drains its pre-trained
weights and invents named entities absent from the ``<archives>`` (playtest
"Eleanor" -> "Perrin Sequence", "née à Höllvania").  This module is the ONLY
deterministic protection: every capitalized NAMED ENTITY of the generated
answer must appear in the retrieved context, in any accent, number or gender
spelling (:func:`lexeme_forms`).  Ordinary vocabulary — a Codex
field label ("Motivations", "Stratégie"), a word the narrative already
spells lowercase, or a common noun the French article contracts before
("l'Empire Orokin") — is a layout artifact, not an entity, and never
triggers the gate.  An answer introducing unsupported entities is replaced
with the abstention chain.

The pure gate grounds on the RAG ``<archives>`` context ONLY; when an archive
vocabulary is wired (:func:`verify_answer_with_archive`) the ground truth
widens to every ingested page, so a faithful sheet is not rejected for naming
an in-universe common noun archived elsewhere — a name absent from EVERY page
stays a confabulation.  Never the persona, which carries a game-wide Warframe
vocabulary ("Margulis", "Zariman", "Sentient") that would let confabulations
through.  A small structural allow list (Codex field labels, story pagination)
covers the fixed formatting scaffold imposed by the persona; speaker metadata
is passed per call.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .vocabulary import ArchiveVocabulary

# Markdown artifacts stripped before entity extraction.
_MD_CLEAN = re.compile(r"[*_>`#\-\[\](){}~]")
# Sentence (and field) boundary: punctuation + whitespace.  The colon is
# included so a Codex field value ("Statut Mnémonique : Décédée") reads as a
# sentence start and its value is never entity-checked.
_BOUNDARY = re.compile(r"[.!?:]\s+")
# A capitalized word, French/English, ≥2 chars ("J'", "L'", digits excluded).
_CAPWORD = re.compile(r"\b([A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-Þà-öø-ÿ]{1,})\b")

# Accent folding: French orthographic variants of the same word
# ("Indifférence" ↔ "Indifference") must resolve to the archived spelling.
# Applied to BOTH sides — entity, curated lists and corpus — so the fold never
# depends on which spelling the model happened to pick.
_ACCENT_MAP = str.maketrans(
    "àâäáãåçèéêëẽíìîïñòóôõöùúûüýÿ",
    "aaaaaaceeeeeiiiinooooouuuuyy",
)


def _fold(text: str) -> str:
    """Accent-free form: the model may drop the French diacritics."""
    return text.translate(_ACCENT_MAP)


# Fixed formatting scaffold of the persona (Codex sheet labels + the story
# pagination closing sentence).  Structural, never factual: these words are
# allowed even though they do not live in the retrieved passages.
TRUSTED_ALLOW = frozenset({
    "allégeance", "archive", "capacité", "capacités", "chronologie",
    "classe", "codex", "complète", "complètes", "doctrine", "faits",
    "fabricant", "fiche", "historiques", "manifestations", "mnémonique",
    "origine", "spécifications", "statistiques", "statut", "sous-titre",
    "tactiques", "territoire", "tissage", "type",
})

# Ordinary French narrative vocabulary that the sheet capitalizes as ADAPTIVE
# field labels ("Adapte les champs à l'entité") or as free-form Codex status
# VALUES ("Statut Mnémonique : Déchu, Manipulateur"): a layout artifact, NOT a
# named entity.  Curated top of the playtest « Ballas » — a faithful récit was
# rejected on exactly these generic words although no invented name was
# present.  The adjectives below are ALSO absent from the archive, so the
# whole-corpus vocabulary cannot excuse them; unverified French words still go
# through the lowercase-in-answer signal (:func:`_ordinary_word`), and invented
# names are absent from this list and stay rejected.
_FR_COMMON = frozenset({
    "ancien", "anciens", "conseil", "domination", "énergétique",
    "énergétiques", "espionnage", "militaire", "militaires", "manipulateur",
    "manipulateurs", "manipulatrice", "manipulatrices", "motivation",
    "motivations", "obsédé", "obsédée", "obsédés", "stratégie", "stratégies",
    "traître", "traîtres",
})

# Accent-insensitive lookups: the model may write a curated word without its
# diacritics ("Mnemonique", "Capacites") — BOTH sides are folded, so the
# canonical spelling of the lists above is never a hidden requirement.
_TRUSTED_FOLDED = frozenset(_fold(word) for word in TRUSTED_ALLOW)
_FR_COMMON_FOLDED = frozenset(_fold(word) for word in _FR_COMMON)


def extract_entities(text: str) -> set[str]:
    """Lowercased capitalized words of ``text``, sentence-initial excluded."""
    clean = _MD_CLEAN.sub(" ", text)
    entities: set[str] = set()
    for sentence in _BOUNDARY.split(clean):
        words = _CAPWORD.findall(sentence)
        for word in words[1:]:
            entities.add(word.lower())
    return entities


def _ordinary_word(entity: str, answer: str) -> bool:
    """Ordinary vocabulary, not a proper name (template capital escaped).

    Three independent signals: the word belongs to the curated French
    narrative list (label-only sheet occurrence, playtest « Ballas »); it is
    introduced by a contracted determiner (``l'Empire``, ``d'Alad``) — French
    elides the article before a COMMON noun, never before a proper name in the
    model's grammatical French; or the exact word recurs in LOWERCASE in the
    answer — the sheet capitalizes field labels while the narrative spells the
    same word lowercase, and invented proper names are NEVER lowercase.  The
    comparisons run on accent-folded text: dropped diacritics ("Mnemonique")
    must not turn ordinary vocabulary into a confabulation.
    """
    key = _fold(entity)
    if key in _FR_COMMON_FOLDED:
        return True
    folded_answer = _fold(answer)
    folded = re.escape(key)
    elided = re.compile(rf"\b(?:l|d|qu)['’]\s*{folded}\b", re.IGNORECASE)
    if elided.search(folded_answer):
        return True
    pattern = re.compile(rf"\b{folded}\b", re.IGNORECASE)
    return any(match.group(0).islower()
               for match in pattern.finditer(folded_answer))


def lexeme_forms(entity: str) -> list[str]:
    """Every spelling of the SAME lexeme: accent-folded and inflected.

    French writes one word several ways — the accented spelling
    ("Indifférence"), the plural ("Protoframes"), the feminine of an archived
    masculine ("Distante" for an archived "distant") and the "-ique" adjective
    whose archived form is "-ic" ("britannique" -> "britannic").  Shared with
    the archive vocabulary (:class:`.vocabulary.ArchiveVocabulary`), which
    probes the identical variants in the database.  Every form must still be
    found somewhere, so an invented name ("Perrin", "Zariman") stays
    ungrounded in every spelling.
    """
    stem = entity[:-1] if entity.endswith("s") else entity
    if stem.endswith("e"):
        stem = stem[:-1]
    forms = {entity, stem, stem + "s", stem + "e", stem + "es"}
    forms |= {form.translate(_ACCENT_MAP) for form in forms}
    forms |= {form[:-4] + "ic" for form in forms if form.endswith("ique")}
    return sorted(forms)


def _grounded(entity: str, corpus: str) -> bool:
    """Word is grounded in the (accent-folded) corpus, or as an orthographic
    or inflectional variant of a corpus word (:func:`lexeme_forms`): French
    accented spelling ("Indifférence"), pluralization ("Protoframes"), gender
    ("Distante" / "distant") and the "-ique" adjective of an archived "-ic"
    ("Britannique") are the SAME lexeme as the retrieved passages, not
    confabulations.  Every accepted form must still resolve to a corpus word,
    so invented names ("Perrin", "Zariman") stay rejected.
    """
    return any(form in corpus for form in lexeme_forms(entity))


def verify_answer(answer: str, context: str,
                  extra_allowed: str = "") -> tuple[bool, set[str]]:
    """True when every NAMED entity of ``answer`` appears in ``context``.

    ``extra_allowed`` covers per-turn trusted metadata the model may echo
    (speaker pseudonym/status, targeted era label, Leverian frame name).
    Ordinary vocabulary is never an entity: template-capitalized labels and
    words the narrative spells lowercase bypass the gate, ONLY invented
    proper names absent from the retrieved passages are confabulations.
    Returns ``(True, set())`` for a fully sourced answer, or
    ``(False, unsupported)`` listing the confabulated entities.
    """
    entities = extract_entities(answer)
    allowed = f"{context} {extra_allowed}"
    corpus = _fold(allowed.lower())
    unsupported = {
        entity for entity in entities
        if not _grounded(entity, corpus)
        and _fold(entity) not in _TRUSTED_FOLDED
        and not _ordinary_word(entity, answer)
    }
    return (len(unsupported) == 0, unsupported)


async def verify_answer_with_archive(
        answer: str, context: str,
        vocabulary: ArchiveVocabulary | None = None,
        extra_allowed: str = "") -> tuple[bool, set[str]]:
    """``verify_answer``, then excuse words the WHOLE archive contains.

    The retrieved passages are a narrow slice: a faithful sheet legitimately
    names in-universe common nouns and real entities archived on OTHER pages
    ("l'Empire", "le Conclave", "Entrati") that the local gate would reject.
    The archive-wide vocabulary is the wider ground truth; a name absent from
    every page stays a confabulation.  ``vocabulary=None`` degrades to the
    pure local gate (DB-less consumers, tests).
    """
    ok, unsupported = verify_answer(answer, context, extra_allowed)
    if ok or vocabulary is None:
        return ok, unsupported
    remaining = await vocabulary.unknown(unsupported)
    return (not remaining, remaining)


__all__ = [
    "TRUSTED_ALLOW",
    "extract_entities",
    "lexeme_forms",
    "verify_answer",
    "verify_answer_with_archive",
]
