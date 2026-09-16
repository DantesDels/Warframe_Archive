"""Deterministic post-generation confabulation gate.

Prompt-level guard rails (``HALLUCINATION_GUARD``, ``STORY_DIRECTIVE`` …)
depend on model obedience, which fails: the model drains its pre-trained
weights and invents named entities absent from the ``<archives>`` (playtest
"Eleanor" -> "Perrin Sequence", "née à Höllvania").  This module is the ONLY
deterministic protection: every capitalized word of the generated answer
must appear in the retrieved context.  An answer introducing unsupported
entities is replaced with the abstention chain.

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

def extract_entities(text: str) -> set[str]:
    """Lowercased capitalized words of ``text``, sentence-initial excluded."""
    clean = _MD_CLEAN.sub(" ", text)
    entities: set[str] = set()
    for sentence in _BOUNDARY.split(clean):
        words = _CAPWORD.findall(sentence)
        for word in words[1:]:
            entities.add(word.lower())
    return entities


def verify_answer(answer: str, context: str,
                  extra_allowed: str = "") -> tuple[bool, set[str]]:
    """True when every entity of ``answer`` appears in ``context``.

    ``extra_allowed`` covers per-turn trusted metadata the model may echo
    (speaker pseudonym/status, targeted era label, Leverian frame name).
    Returns ``(True, set())`` for a fully sourced answer, or
    ``(False, unsupported)`` listing the confabulated entities.
    """
    entities = extract_entities(answer)
    allowed = f"{context} {extra_allowed}"
    corpus = allowed.lower()
    unsupported = {
        entity for entity in entities
        if entity not in corpus and entity not in TRUSTED_ALLOW
    }
    return (len(unsupported) == 0, unsupported)


__all__ = ["TRUSTED_ALLOW", "extract_entities", "verify_answer"]
