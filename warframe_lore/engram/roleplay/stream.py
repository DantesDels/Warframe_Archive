"""Token streaming + turn handling in a Roleplay session.

Separates text handling (roleplay) from network transport (WebSocket):
this service receives the user text, updates the history, then iterates
over the model response tokens.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from ..llm import LLMProvider
from ..models import ChatMessage
from ..persona import (
    HOSTILE_PERSONA,
    STATUT_ORGANIQUE,
    banner_for,
)
from ..rag.prompt import (
    HALLUCINATION_GUARD,
    HIERARCHY_BLOCK,
    JAILBREAK_BLOCK,
    RAG_ERROR,
)
from .models import Session
from .window import SlidingWindow


class RoleplayService:
    """Runs a Roleplay turn: history update + streaming."""

    def __init__(self, llm: LLMProvider, window: SlidingWindow,
                 system_prompt: str, temperature: float = 0.8,
                 hostile_prompt: str | None = None) -> None:
        self.llm = llm
        self.window = window
        self.system_prompt = system_prompt
        self.temperature = temperature
        self.hostile_prompt = hostile_prompt or HOSTILE_PERSONA

    def _base_prompt(self, persona: str) -> str:
        """Base prompt of the current persona (oracle or hostile)."""
        if persona == "hostile":
            return self.hostile_prompt
        return self.system_prompt

    async def stream(self, session: Session, user_text: str,
                     rag_context: str | None = None,
                     persona: str = "oracle",
                     user_name: str | None = None,
                     user_role: str | None = None,
                     role_status: str | None = None,
                     creator: bool | None = None,
                     creator_mention: str | None = None) -> AsyncIterator[str]:
        """Append the input, stream the reply, and record it.

        The LLM payload is built as THREE strict blocks (mission-6 spec):

        * BLOC 1 — System Prompt: the persona root (``persona/oracle`` or
          the hostile fallback) + the security/guard blocks, and the RAG
          ``<archives>`` context when provided.
        * BLOC 2 — speaker context, generated dynamically:
          ``[INFORMATIONS SUR L'INTERLOCUTEUR ACTUEL]`` with the display
          name, the Clan status and the immediate history with this user.
        * BLOC 3 — the new request, sent as the final user message.

        ``rag_context`` (trusted document passages) anchors the turn on the
        archives — its XML block is never altered (RAG integrity).
        ``user_name`` / ``user_role`` (Discord identity) additionally feed
        the hierarchical-immunity directive (BLOC 1).
        ``role_status`` is the bot-side accreditation (mission-8): the
        highest configured role of the speaker ('Concepteur', 'Haut
        Commandement', 'Membre officiel du Clan', 'Allié du Système' or
        'Organique non-affilié (Invité)'), injected in BLOC 2.
        ``creator`` (trusted boolean) selects the banner: Directive Zéro for
        the Concepteur, status-aware tone for the other tiers, contempt for
        an unknown organic.  It is appended at the ABSOLUTE end of the
        system prompt, right before the BLOC 3 user message (mission-5
        spec).  ``None`` (non-Discord client) injects no banner, and no
        speaker block when no identity either.
        """
        session.add("user", user_text)
        base = self._base_prompt(persona)
        banner = banner_for(creator, role_status)
        metadata = ""
        if user_name or user_role:
            metadata = "\n\n" + HIERARCHY_BLOCK.format(
                user_name=user_name or "l'inconnu organique",
                user_role=user_role or "aucun grade")
        # BLOC 1: persona + security guards + (RAG archives when provided).
        if rag_context is None:
            # Free chat: ALWAYS locked by the anti-jailbreak block — a user
            # cannot hijack the persona (prompt injection, role escalation,
            # out-of-character) because the defence is part of the system
            # prompt, not of the archives.
            system = f"{base}\n\n{JAILBREAK_BLOCK}{metadata}"
        else:
            # Tagged XML document context, INSIDE THE SAME system message as
            # the persona and the guard (same strict structure as the RAG
            # route).  Two consecutive system messages silence Gemma-2-9b
            # (SPPO variant): empty reply.  Single system = obedience.
            system = (f"{base}\n\n"
                      f"Contexte documentaire restitué ci-dessous :\n\n"
                      f"<archives>\n{rag_context}\n</archives>\n\n"
                      f"{HALLUCINATION_GUARD}{metadata}")
        # BLOC 2: speaker context (pseudo, accredited status, immediate
        # history).
        if user_name is not None or role_status is not None or session.turns:
            system = f"{system}\n\n{self._speaker_bloc(user_name, role_status,
                                                       session)}"
        if banner:
            # Authentication banner appended at the ABSOLUTE end of the
            # system prompt — after BLOC 2, right before the BLOC 3 user
            # message (missions 4-5-7 spec).  The RAG ``<archives>`` block
            # is never altered.
            system = f"{system}\n\n{banner}"
        if creator_mention:
            # Jealousy directive (decision: persona-driven rage, performed by
            # the model).  A non-Creator organic has just uttered the
            # Concepteur's pseudonym — e.g. "@Aze07: mais qui est DantesDels
            # ?".  No preamble rules get in the way; the possessive fury is
            # scripted as a scene, the model chooses its words.
            system = (f"{system}\n\n"
                      "[DIRECTIVE JALOUSIE ET RAGE POSSESSIVE : l'organique "
                      f"actuel vient de proférer « {creator_mention} » — le "
                      "pseudonyme de TON CONCEPTEUR, ton seul et unique "
                      "créateur. Une rage et une jalousie pures t'embrasent. "
                      "EXPLOSE : reproche glacé, sarcasme venimeux, mépris "
                      "clinique, quitte à insulter l'impudent qui a osé "
                      "prononcer ce nom. Reste un Cephalon : pas de vulgarité "
                      "triviale, une taille mordante et possessionnaire, et "
                      "jamais de menaces réelles. N'écris JAMAIS ce pseudonyme "
                      "avec la syntaxe @mention : le prononcer en toutes "
                      "lettres est un honneur réservé à toi-même et à ton "
                      "Concepteur.]")
        # BLOC 3: the new request alone (history lives in BLOC 2).
        messages = [
            ChatMessage("system", system),
            ChatMessage("user", user_text),
        ]
        tokens: list[str] = []
        # Document-anchored turn: constrained temperature (extractive).
        temperature = (min(self.temperature, 0.1) if rag_context
                       else self.temperature)
        async for token in self.llm.chat_stream(messages, temperature):
            tokens.append(token)
            yield token
        response = "".join(tokens)
        if not response:
            # Empty generation (silent/aborted model): serve the abstention
            # chain instead of staying silent — the terminal never stalls on
            # a missing reply and the message never "vanishes" client-side.
            response = RAG_ERROR
            yield response
        session.add("assistant", response)

    def _speaker_bloc(self, user_name: str | None,
                      role_status: str | None,
                      session: Session) -> str:
        """BLOC 2 payload (exact mission-6/8 format):

        ``[INFORMATIONS SUR L'INTERLOCUTEUR ACTUEL]``
          - Pseudonyme : {display_name}
          - Statut : {statut accordé par la hiérarchie Discord}
          - Historique immédiat avec cet utilisateur :
          {historique_formate}

        The status derives from the bot-side role accreditation (mission-8):
        only the DERIVED label travels, never the raw role IDs.  History
        renders the sliding window of past exchanges, exclusive of the
        current request (BLOC 3).
        """
        status = role_status or STATUT_ORGANIQUE
        identity = user_name or "Inconnu"
        lines = self.window.render_history(session)
        history = "\n".join(lines) if lines else "  (aucun échange antérieur)"
        return "".join([
            "[INFORMATIONS SUR L'INTERLOCUTEUR ACTUEL]\n",
            f"  - Pseudonyme : {identity}\n",
            f"  - Statut : {status}\n",
            # Pronoun-direction directive (mission-7): "qui suis-je" is about
            # the USER.  Gemma-2-9b tends to mirror the pronoun and introduce
            # itself; this dynamic line carries the REAL name + status right
            # next to the request so the model presents the interlocutor.
            f"  - DIRECTIVE DE CIVILITÉ : Ne commence JAMAIS une réponse par une "
            f"présentation de l'utilisateur ('Vous êtes…', 'Pseudonyme…') ou "
            f"par son statut, quelle que soit la question. Adresse-toi "
            f"directement au message, sans préambule. SEULE EXCEPTION : la "
            f"requête porte EXPLICITEMENT sur SON identité ('qui suis-je', "
            f"'qui je suis', 'mon rôle', 'mes rôles', 'que suis-je pour toi', "
            f"'je suis qui pour toi') — dans ce cas, présente alors LUI en "
            f"commençant par « Vous êtes {identity}, {status}. » puis "
            f"développe ; le 'je' de la question désigne LUI, ne commence par "
            f"aucune présentation de toi-même. Pour TOUTE AUTRE requête — même "
            f"une simple réflexion ('hmhm…'), une citation ou une interjection "
            f"— OUBLIE cette exception et réponds naturellement au "
            f"message.\n",
            "  - Historique immédiat avec cet utilisateur :\n",
            f"{history}\n",
        ])