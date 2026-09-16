"""Deterministic post-generation confabulation gate.

Prompt-level guard rails (``HALLUCINATION_GUARD``, ``STORY_DIRECTIVE`` …)
depend on model obedience, which fails: the model drains its pre-trained
weights and invents named entities absent from the ``<archives>`` (playtest
"Eleanor" -> "Perrin Sequence", "née à Höllvania").  This module is the ONLY
deterministic protection: every capitalized NAMED ENTITY of the generated
answer must appear in the retrieved context.  Ordinary vocabulary — a Codex
field label ("Motivations", "Stratégie"), a word the narrative already
spells lowercase, or a common noun the French article contracts before
("l'Empire Orokin") — is a layout artifact, not an entity, and never
triggers the gate.  An answer introducing unsupported entities is replaced
with the abstention chain.

The corpus is the RAG ``<archives>`` context ONLY — never the persona, which
carries a game-wide Warframe vocabulary ("Margulis", "Zariman", "Sentient")
that would let confabulations through.  A small structural allow list
(Codex field labels, story pagination) covers the fixed formatting scaffold
imposed by the persona; speaker metadata is passed per call.
"""

from __future__ import annotations

import re

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
_ACCENT_MAP = str.maketrans(
    "àâäáãåçèéêëẽíìîïñòóôõöùúûüýÿ",
    "aaaaaaceeeeeiiiinooooouuuuyy",
)

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
# field labels ("Adapte les champs à l'entité"): a layout artifact, NOT a
# named entity.  Curated top of the playtest « Ballas » — a faithful récit was
# rejected on exactly these generic words although no invented name was
# present.  Unverified French words still go through the lowercase-in-answer
# signal (:func:`_ordinary_word`); invented names are absent from this list
# and stay rejected.
_FR_COMMON = frozenset({
    "ancien", "anciens", "conseil", "domination", "espionnage", "militaire",
    "militaires", "motivation", "motivations", "obsédé", "obsédée",
    "obsédés", "stratégie", "stratégies", "traître", "traîtres",
})

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

    Three independent signals: the exact word recurs in LOWERCASE in the
    answer — the sheet capitalizes field labels while the narrative spells
    the same word lowercase, and invented proper names are NEVER lowercase;
    the word belongs to the curated French narrative list (label-only sheet
    occurrence, playtest « Ballas »); or it is introduced by a contracted
    determiner (``l'Empire``, ``d'Alad``) — French elides the article before
    a COMMON noun, never before a proper name in the model's grammatical
    French.  The lowercase signal is language-agnostic; the list and the
    elision are French-only.
    """
    if entity in _FR_COMMON:
        return True
    elided = re.compile(
        rf"\b(?:l|d|qu)['’]\s*{re.escape(entity)}\b", re.IGNORECASE)
    if elided.search(answer):
        return True
    pattern = re.compile(rf"\b{re.escape(entity)}\b", re.IGNORECASE)
    return any(match.group(0).islower() for match in pattern.finditer(answer))


def _candidates(entity: str) -> list[str]:
    """Grounded forms: the word, its accented folded form, and (for a plural)
    the singular of each.  French adjectives in ``-ique`` are also folded to
    their archived ``-ic`` spelling (``britannique`` -> ``britannic``).
    All must be checked against the verbatim corpus."""
    forms = [entity, entity.translate(_ACCENT_MAP)]
    if entity.endswith("s"):
        singular = entity[:-1]
        forms.extend((singular, singular.translate(_ACCENT_MAP)))
    folded = list(forms)
    for form in folded:
        if form.endswith("ique"):
            forms.append(form[:-4] + "ic")
    return forms


def _grounded(entity: str, corpus: str) -> bool:
    """Word is grounded verbatim, or as an orthographic variant of a
    corpus word: French accented spelling ("Indifférence"), French
    pluralization ("Protoframes") and French adjectives in "-ique"
    ("Britannique") of archived terms are the SAME lexeme as the retrieved
    passages, not confabulations.  Every accepted form must still resolve
    to a verbatim corpus word, so invented names ("Perrin", "Zariman")
    stay rejected.
    """
    return any(form in corpus for form in _candidates(entity))


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
    corpus = allowed.lower()
    unsupported = {
        entity for entity in entities
        if not _grounded(entity, corpus)
        and entity not in TRUSTED_ALLOW
        and not _ordinary_word(entity, answer)
    }
    return (len(unsupported) == 0, unsupported)


__all__ = ["TRUSTED_ALLOW", "extract_entities", "verify_answer"]
