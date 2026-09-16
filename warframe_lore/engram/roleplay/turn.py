"""One roleplay message turn: the deterministic short-circuits before the LLM.

Decides whether a ``message`` frame can be answered WITHOUT the model — hostile
probe, archives missing, guild-member question, speaker-identity question — else
hands back the retrieved passages.  Transport stays in the router, the reply
texts live in :mod:`replies`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from warframe_lore.protocols.roleplay import PERSONA_ORACLE

from ..rag import (
    JAILBREAK_REJECT,
    RAG_ERROR,
    RAGContext,
    detect_probe,
    is_identity_question,
    is_self_reflection,
)
from .replies import external_organic_reply, identity_reply, member_roster_reply

if TYPE_CHECKING:
    from ..api.container import Container


@dataclass(frozen=True)
class TurnPlan:
    """Outcome of the pre-LLM analysis of one ``message`` frame."""

    # Deterministic answer: the model is never called for this turn.
    reply: str | None = None
    # Retrieved passages anchoring the LLM turn (``None`` = free chat).
    context_text: str | None = None


async def plan_turn(container: Container, payload: dict, user_text: str,
                    persona_mode: str, rag_context: RAGContext) -> TurnPlan:
    """Run the short-circuits in order, else prepare the archives context."""
    # HOSTILE PROBE (SQL injection, privilege escalation, third-party mention):
    # the exact anti-jailbreak chain, without embedding nor LLM call.
    if detect_probe(user_text):
        return TurnPlan(reply=JAILBREAK_REJECT)
    # Introspection (the Oracle itself, its creator) never grounds on the
    # archives: the consciousness exception applies, and the no-passage
    # short-circuit must not answer "Données insuffisantes" there.
    # A storyteller request is ALWAYS archive-grounded (when the bot did not
    # already tag it ``rag``): the narrative must follow the documented lore.
    want_rag = bool(payload.get("rag") or payload.get("story")) \
        and not is_self_reflection(user_text)
    context_text = suggestion = None
    if want_rag:
        context_text, suggestion = await container.rag.resolve(
            user_text, context=rag_context,
            subject=payload.get("targeted_subject"))
    if want_rag and not context_text and (suggestion is None
                                          or payload.get("story")):
        # A disambiguation suggestion cannot ANCHOR a narration: a story
        # without passages would be invented from nothing, so it refuses
        # exactly like any query left without a trusted passage.
        return TurnPlan(reply=RAG_ERROR)
    reply = (member_reply(payload, persona_mode)
             or identity_reply_for(payload, user_text, persona_mode))
    if reply:
        return TurnPlan(reply=reply)
    return TurnPlan(context_text=context_text)


def member_reply(payload: dict, persona_mode: str) -> str | None:
    """Deterministic answer about a GUILD MEMBER ("Qui est Aze ?").

    The bot resolved the pseudo and sent ``member_name``: the persona's GESTION
    DES ORGANIQUES EXTERNES answers — factual, cold disdain, NEVER the archives
    ("Données insuffisantes" was the playtest bug) nor the RAG.
    """
    member_name = payload.get("member_name")
    if persona_mode != PERSONA_ORACLE or not member_name:
        return None
    affiliated = payload.get("member_affiliated")
    accredited = {
        "affiliated": True if affiliated is None else bool(affiliated),
        "creator": bool(payload.get("creator")),
        "reluctant": bool(payload.get("reluctant")),
    }
    roles = payload.get("member_roles")
    if roles is not None:
        return member_roster_reply(str(member_name), list(roles),
                                   **accredited)
    return external_organic_reply(str(member_name), **accredited)


def identity_reply_for(payload: dict, user_text: str,
                       persona_mode: str) -> str | None:
    """Deterministic answer to a speaker-identity question ("qui suis-je ?").

    Built from the accredited data (BLOC 2 identity): the devotion persona keeps
    self-introducing instead of presenting the speaker, so the model is never
    called.  Anonymous clients fall back to the LLM turn, and the hostile persona
    keeps insisting (the attacker must apologise, whatever the question).
    """
    if persona_mode != PERSONA_ORACLE or not is_identity_question(user_text):
        return None
    return identity_reply(user_name=payload.get("user_name"),
                          user_role=payload.get("user_role"),
                          user_roles=payload.get("user_roles"),
                          role_status=payload.get("role_status"),
                          creator=bool(payload.get("creator")))


__all__ = ["TurnPlan", "identity_reply_for", "member_reply", "plan_turn"]
