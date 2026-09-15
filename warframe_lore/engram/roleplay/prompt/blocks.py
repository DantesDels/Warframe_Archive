"""Assembly of the strict three-block Roleplay payload.

BLOC 1 (persona root + security guards + the RAG ``<archives>`` context) and the
trailing directives (authentication banner, jealousy, answer language) are pure
string assembly — kept out of the turn runner so the prompt structure reads in
one place.  The ``<archives>`` block is never altered (RAG integrity).
"""

from __future__ import annotations

from ...auth import banner_for
from ...rag import HALLUCINATION_GUARD, HIERARCHY_BLOCK, JAILBREAK_BLOCK
from .directives import JEALOUSY_DIRECTIVE, language_directive

ARCHIVES_HEADER = "Contexte documentaire restitué ci-dessous :"


def archive_bloc(base_prompt: str, rag_context: str | None,
                 user_name: str | None, user_role: str | None) -> str:
    """BLOC 1: persona root + guard (+ archives) + hierarchy metadata."""
    metadata = ""
    if user_name or user_role:
        metadata = "\n\n" + HIERARCHY_BLOCK.format(
            user_name=user_name or "l'inconnu organique",
            user_role=user_role or "aucun grade")
    if rag_context is None:
        # Free chat: ALWAYS locked by the anti-jailbreak block — a user cannot
        # hijack the persona, because the defence is part of the system prompt.
        return f"{base_prompt}\n\n{JAILBREAK_BLOCK}{metadata}"
    # Tagged XML context INSIDE THE SAME system message as the persona and the
    # guard: two consecutive system messages silence Gemma-2-9b (SPPO variant).
    return (f"{base_prompt}\n\n{ARCHIVES_HEADER}\n\n"
            f"<archives>\n{rag_context}\n</archives>\n\n"
            f"{HALLUCINATION_GUARD}{metadata}")


def turn_directives(system: str, creator: bool | None,
                    role_status: str | None, creator_mention: str | None,
                    lang: str | None) -> str:
    """Append the banner, then the jealousy and language directives.

    The banner sits at the ABSOLUTE end of the prompt (after BLOC 2), right
    before the BLOC 3 user message; the other directives follow it only when
    the turn requires them.
    """
    banner = banner_for(creator, role_status)
    if banner:
        system = f"{system}\n\n{banner}"
    if creator_mention:
        system = (f"{system}\n\n"
                  f"{JEALOUSY_DIRECTIVE.format(mention=creator_mention)}")
    directive = language_directive(lang)
    if directive:
        system = f"{system}\n\n{directive}"
    return system


__all__ = ["ARCHIVES_HEADER", "archive_bloc", "turn_directives"]
