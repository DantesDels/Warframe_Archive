"""Story-turn double pass: invisible factual draft, then the narration system.

A narrative turn grounded on archives runs TWO LLM calls.  Pass 1
(:func:`fetch_factual_draft`) is an INVISIBLE extraction: a French-only,
cold (0.1) call that turns the archives into a raw factual draft, never
served on the wire.  Pass 2 (:func:`story_turn_system`) assembles the final
system prompt: the era/lens directive, the "no repetition" expansion rule
and the draft — or the plain directive when no archive grounds the turn.

The two French locks (draft AND narration) live here so the double pass is
one single source of truth, and the duplicated directive selection of the
classic two-branch assembly is a single function.
"""

from __future__ import annotations

import logging

from ..llm import LLMProvider
from ..models import ChatMessage
from .prompt import (
    leverian_directive,
    story_directive,
    targeted_story_directive,
)

# Pass 1: the extraction directive.  The draft is French-only even when the
# archives are English — the model translates, never copies.
FACTUAL_DRAFT_DIRECTIVE = (
    "DIRECTIVE DRAFT FACTUEL : Extrais l'intégralité des "
    "événements, détails, et actions présents dans ces archives. "
    "NE RÉSUME PAS. Conserve absolument toute la richesse, la "
    "longueur et les nuances des informations. Rédige un brouillon "
    "brut, chronologique et très détaillé. LE BROUILLON EST "
    "RÉDIGÉ EN FRANÇAIS : même si les archives sont en anglais, "
    "traduis les faits en français — jamais de brouillon en "
    "anglais."
)

# Pass 2: the expansion rule.  The directive forbids repeating what the
# history already told; the output language stays French even when the draft
# is English — translated, never recopied.
STORY_EXPANSION_DIRECTIVE = (
    "DIRECTIVE DE NARRATION (SUITE) : Utilise le brouillon suivant "
    "comme base pour le récit. RÈGLE ABSOLUE : NE RÉPÈTE JAMAIS, "
    "sous aucun prétexte, les événements ou les phrases que tu as "
    "déjà racontés dans tes messages précédents (historique de "
    "conversation). Concentre-toi UNIQUEMENT sur la narration des "
    "NOUVEAUX éléments présents dans le brouillon. Développe ce "
    "nouveau passage de manière immersive, théâtrale et détaillée. "
    "LA LANGUE DE SORTIE EST LE FRANÇAIS : rédige le récit en "
    "français même si le brouillon factuel est en anglais — "
    "traduis-le, ne le recopie jamais."
)

log = logging.getLogger("warframe_lore.engram.roleplay.story_turn")


async def fetch_factual_draft(llm: LLMProvider, user_text: str,
                              rag_context: str) -> str:
    """Pass 1: the invisible factual extraction (temp 0.1, French-locked).

    Building the draft messages, then streams the extraction call.  A failure
    keeps the fallback phrase so the narration can still run — the draft is
    never served, only embedded in the Pass 2 system prompt.
    """
    draft_messages = [
        ChatMessage(
            "system",
            FACTUAL_DRAFT_DIRECTIVE + f"\n\n<archives>\n{rag_context}\n</archives>",
        ),
        ChatMessage("user", user_text),
    ]
    draft_tokens: list[str] = []
    # The fallback draft is only kept when the extraction call fails.
    factual_draft = "Erreur de génération du brouillon."
    try:
        # Pure extraction LLM call (temp 0.1)
        async for token in llm.chat_stream(draft_messages, 0.1):
            draft_tokens.append(token)
        factual_draft = "".join(draft_tokens)
    except Exception as exc:  # noqa: BLE001 (LLM down -> fallback)
        log.error("Roleplay generation failed on Draft Pass (%s)", exc)
    return factual_draft


def story_turn_system(base_system: str, factual_draft: str | None, *,
                      story_lens: str | None,
                      targeted_era: str | None,
                      leverian_warframe: str | None,
                      story_continuation: bool,
                      story_more: bool) -> str:
    """Pass 2: the final narration system prompt of a story turn.

    The directive is era-anchored when the request named a subject, lens-based
    otherwise.  A draft extends the system with the expansion rule and the
    draft itself; ``None`` keeps the plain directive (story without archives).
    The Leverian source lock is appended when a Warframe gallery is set.
    """
    if targeted_era:
        directive = targeted_story_directive(
            targeted_era, continuation=story_continuation, more=story_more)
    else:
        directive = story_directive(
            story_lens, continuation=story_continuation, more=story_more)
    if factual_draft is None:
        system = f"{base_system}\n\n{directive}"
    else:
        system = (
            f"{base_system}\n\n{directive}\n\n{STORY_EXPANSION_DIRECTIVE}\n\n"
            f"[BROUILLON FACTUEL À DÉVELOPPER :]\n{factual_draft}"
        )
    if leverian_warframe:
        system = f"{system}\n\n{leverian_directive(leverian_warframe)}"
    return system


__all__ = ["STORY_EXPANSION_DIRECTIVE", "fetch_factual_draft",
           "story_turn_system"]
