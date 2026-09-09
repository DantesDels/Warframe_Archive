"""Streaming token + gestion du tour dans une session Roleplay.

Sépare la correction du texte (roleplay) du transport réseau (WebSocket) :
ce service reçoit le texte de l'utilisateur, met à jour l'historique, puis
itère les tokens de la réponse du modèle.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from ..llm import LLMProvider
from ..models import ChatMessage
from ..persona import HOSTILE_PERSONA
from ..rag.prompt import HALLUCINATION_GUARD, JAILBREAK_BLOCK, RAG_ERROR
from .models import Session
from .window import SlidingWindow


class RoleplayService:
    """Déroule un tour Roleplay : mise à jour d'historique + streaming."""

    def __init__(self, llm: LLMProvider, window: SlidingWindow,
                 system_prompt: str, temperature: float = 0.8,
                 hostile_prompt: str | None = None) -> None:
        self.llm = llm
        self.window = window
        self.system_prompt = system_prompt
        self.temperature = temperature
        self.hostile_prompt = hostile_prompt or HOSTILE_PERSONA

    def _base_prompt(self, persona: str) -> str:
        """Prompt de base du persona courant (oracle ou hostile)."""
        if persona == "hostile":
            return self.hostile_prompt
        return self.system_prompt

    async def stream(self, session: Session, user_text: str,
                     rag_context: str | None = None,
                     persona: str = "oracle") -> AsyncIterator[str]:
        """Append la saisie, streame la réponse, et enregistre celle-ci.

        ``rag_context`` (passages documentaires de confiance) fusionne un
        contexte externe dans le prompt : ordre petit-modèle (contexte,
        persona, garde anti-hallucination, puis fenêtre de dialogue).
        ``persona`` sélectionne le persona de la session : ``"oracle"``
        (défaut) ou ``"hostile"`` (mode anti-agression, voir ``persona.py``).
        """
        session.add("user", user_text)
        base = self._base_prompt(persona)
        if rag_context is None:
            # Chat libre : TOUJOURS verrouillé par le bloc anti-jailbreak —
            # un utilisateur ne peut pas détourner le persona (prompt
            # injection, élévation de rôle, sortie de personnage) car la
            # défense fait partie du prompt système, pas des archives.
            system = f"{base}\n\n{JAILBREAK_BLOCK}"
            messages = self.window.to_messages(session, system)
        else:
            # Contexte documentaire balisé XML, DANS LE MÊME message système
            # que le persona et le garde (même structure stricte que la route
            # RAG).  Deux messages système consécutifs font taire Gemma-2-9b
            # (variante SPPO) : réponse vide.  Système unique = obéissance.
            system = (f"{base}\n\n"
                      f"Contexte documentaire restitué ci-dessous :\n\n"
                      f"<archives>\n{rag_context}\n</archives>\n\n"
                      f"{HALLUCINATION_GUARD}")
            messages = [
                ChatMessage("system", system),
                *self.window.bounded_turns(session),
            ]
        tokens: list[str] = []
        # Tour ancré documentairement : température bridée (extractif).
        temperature = (min(self.temperature, 0.1) if rag_context
                       else self.temperature)
        async for token in self.llm.chat_stream(messages, temperature):
            tokens.append(token)
            yield token
        response = "".join(tokens)
        if not response:
            # Génération vide (modèle silencieux/avorté) : on sert la chaîne
            # d'abstention au lieu de ne rien dire — le terminal ne reste
            # jamais bloqué sur une réponse inexistante et le message ne
            # "disparaît" pas du côté du client Discord.
            response = RAG_ERROR
            yield response
        session.add("assistant", response)