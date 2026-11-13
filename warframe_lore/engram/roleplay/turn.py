"""One roleplay message turn: the deterministic short-circuits before the LLM.

Decides whether a ``message`` frame can be answered WITHOUT the model — hostile
probe, archives missing, guild-member question, speaker-identity question,
disambiguation request for an ambiguous subject — else hands back the retrieved
passages.  Transport stays in the router, the reply texts live in :mod:`replies`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from warframe_lore.core.protocols.roleplay import PERSONA_ORACLE
from warframe_lore.engram.rag import (
    JAILBREAK_REJECT,
    RAG_ERROR,
    RAGContext,
    detect_probe,
    is_identity_question,
    is_self_reflection,
    sanitize_query,
)
from warframe_lore.engram.roleplay.prompt import STORY_COMPLETE_SENTENCE
from warframe_lore.engram.roleplay.replies import (
    external_organic_reply,
    identity_reply,
    member_roster_reply,
)

if TYPE_CHECKING:
    from warframe_lore.engram.api.container import Container


# Deterministic disambiguation reply: a close page title was found but no
# trusted passage supports an answer — refusing outright (RAG_ERROR) wastes the
# hit, so the bot asks the user to confirm the exact subject (the "doute ->
# précisions" flow).  The CONFIRMED subject then grounds the next turn on real
# passages; a bare suggestion never anchors a Codex sheet nor a narration.
CLARIFY_REPLY = ("Voulez-vous dire « {suggestion} » ? Précisez l'entité "
                 "exacte pour que j'ouvre ses archives, organique.")

# Continuation of a narrative whose dossier is EXHAUSTED: the cursor points
# past the last page, so no passage can anchor another part.  "Données
# insuffisantes" would read as a missing-data bug; the archivist closing
# sentence is exactly the one the parts already use to end a tale.
STORY_EXHAUSTED_REPLY = STORY_COMPLETE_SENTENCE


@dataclass(frozen=True)
class TurnPlan:
    """Outcome of the pre-LLM analysis of one ``message`` frame."""

    # Deterministic answer: the model is never called for this turn.
    reply: str | None = None
    # Retrieved passages anchoring the LLM turn (``None`` = free chat).
    context_text: str | None = None
    # Narrative pagination: the subject's dossier still holds unseen passages
    # (the client may chain another part).
    story_more: bool = False


async def plan_turn(container: Container, payload: dict, user_text: str,
                    persona_mode: str, rag_context: RAGContext,
                    consumed_chunk_ids: set[int] | None = None) -> TurnPlan:
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
    story_more = False

    # A caller without an exclusion memory starts with an empty ban set.
    if consumed_chunk_ids is None:
        consumed_chunk_ids = set()

    if want_rag:
        # A CONTINUATION of an open narrative names no subject of its own
        # ("continue"): the bot sends the request that anchored the story and
        # the SEARCH runs on it.  The model still receives the user's wording.
        # ``dossier_offset`` marks a continuation; the session's consumed ids
        # exclude the chunks the previous parts already narrated.
        search_text = sanitize_query(
            str(payload.get("retrieval_text") or user_text))

        # Pass the ban list and collect the newly consumed chunk ids.
        context_text, suggestion, story_more, new_ids = await container.rag.resolve(
            search_text, context=rag_context,
            subject=payload.get("targeted_subject"),
            offset=int(payload.get("dossier_offset") or 0),
            exclude_ids=list(consumed_chunk_ids),
            story=bool(payload.get("story"))
        )

        # Grow the session's exclusion memory with what the model really saw.
        consumed_chunk_ids.update(new_ids)

    if want_rag and suggestion is not None:
        # A partial title match is NOT a trusted passage.  The [SUGGESTION]
        # marker must never reach the model: the roleplay prompt has no
        # disambiguation directive, so the Codex template would be filled from
        # pre-trained weights (playtest « Zikhaio Nuri »).  The doubt resolves
        # by precision instead, and the confirmed subject grounds the next
        # turn — a tale included.
        return TurnPlan(reply=CLARIFY_REPLY.format(suggestion=suggestion))

    if want_rag and not context_text:
        # No trusted passage: the LLM is NEVER called, free chat included — a
        # forced Codex sheet would be invented from nothing.  A continuation of
        # a drained narrative closes with the archivist sentence instead.
        if story_more is False and int(payload.get("dossier_offset") or 0) > 0:
            return TurnPlan(reply=STORY_EXHAUSTED_REPLY)
        return TurnPlan(reply=RAG_ERROR)

    reply = (member_reply(payload, persona_mode)
             or identity_reply_for(payload, user_text, persona_mode))
    if reply:
        return TurnPlan(reply=reply)

    return TurnPlan(context_text=context_text, story_more=story_more)


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


__all__ = ["CLARIFY_REPLY", "STORY_EXHAUSTED_REPLY", "TurnPlan",
           "identity_reply_for", "member_reply", "plan_turn"]
