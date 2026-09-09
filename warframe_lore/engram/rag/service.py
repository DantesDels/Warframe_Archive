"""Service RAG documentaire : embedding -> récupération -> prompt -> LLM.

Haut niveau : ne dépend que d'abstractions injectées (``EmbeddingProvider``,
``Retriever``, ``LLMProvider``) — jamais d'un stockage ou d'un client concret
(principe D).  Le point d'accès aux données vit derrière :class:`Retriever`.
Audit : chaque requête journalise le contexte extrait de pgvector avant son
envoi au LLM, pour isoler un manque de données (ETL) d'une désobéissance
du modèle.  Short-circuit : sans passage de confiance, le LLM n'est jamais
appelé — la chaîne exacte :const:`RAG_ERROR` est retournée directement.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from ..llm import EmbeddingProvider, LLMProvider
from ..models import ChatMessage
from .aliases import resolve_alias
from .prompt import NO_DATA_MARKER, PromptBuilder, RAG_ERROR, RAGPrompt
from .retriever import RAGHit, Retriever

log = logging.getLogger("warframe_lore.engram.rag")

# Température d'inférence RAG : 0.0 -> comportement purement extractif.
RAG_TEMPERATURE = 0.0


class RAGService:
    """Orchestre une requête RAG documentaire de bout en bout."""

    def __init__(self, embeddings: EmbeddingProvider, retriever: Retriever,
                 llm: LLMProvider, prompt_builder: PromptBuilder,
                 suggestion_min_score: float = 0.5) -> None:
        self.embeddings = embeddings
        self.retriever = retriever
        self.llm = llm
        self.prompt_builder = prompt_builder
        self.suggestion_min_score = suggestion_min_score

    async def retrieve(self, question: str
                       ) -> tuple[list[RAGHit], RAGPrompt, bool]:
        """Assemble le prompt et décide du short-circuit, avec journalisation.

        La requête est d'abord enrichie par ``resolve_alias`` (surnom -> nom
        canonique) pour fiabiliser l'embedding.  ``bypass`` signale l'absence
        de passage de confiance ET de désambiguïsation : le LLM ne doit pas
        être appelé (short-circuit).
        """
        expanded, alias_note, canon = resolve_alias(question)
        query_vector = (await self.embeddings.embed([expanded]))[0]
        hits = await self.retriever.search(query_vector)
        used_hits = hits
        top = hits[0].score if hits else 0.0
        suggestion = None
        if top < self.suggestion_min_score:
            # Recherche trop faible (sujet absent) : ne jamais fonder une
            # réponse sur des voisins hors-sujet.  On tente la désambigui-
            # sation (alias canonique ou titre voisin), sinon on coupe court.
            suggestion = (canon if alias_note
                          else await self._suggest_title(question))
            # Contexte privé de contenu : pas de voisin hors-sujet au LLM.
            used_hits = []
        bypass = not used_hits and suggestion is None
        prompt = self.prompt_builder.build(
            question, used_hits, alias_note=alias_note, suggestion=suggestion)
        log.info("Audit RAG question=%r hit=%d suggestion=%r bypass=%s "
                 "ctx_car=%d ctx=%r...",
                 question, len(hits), suggestion, bypass,
                 len(prompt.context), prompt.context[:180].replace("\n", " "))
        return used_hits, prompt, bypass

    async def resolve(self, question: str
                      ) -> tuple[str | None, str | None]:
        """Contexte/suggestion pour un tour Roleplay (WS).

        ``bypass`` -> ``(None, None)`` : le client WS doit alors short-circuiter
        avec la chaîne d'erreur exacte.  Sinon ``(contexte, suggestion)`` : le
        contexte est sûr (jamais de marqueur vide) ; une ``suggestion`` non nulle
        indique au routeur qu'il concerne la désambiguïsation.
        """
        _, prompt, bypass = await self.retrieve(question)
        if bypass:
            return None, None
        return prompt.context, prompt.suggestion

    async def answer_with_sources(self, question: str
                                  ) -> tuple[str, list[RAGHit]]:
        """Réponse du modèle + passages pertinents (short-circuit sinon)."""
        hits, prompt, bypass = await self.retrieve(question)
        if bypass:
            return RAG_ERROR, []
        messages = [ChatMessage(m["role"], m["content"])
                    for m in prompt.to_messages()]
        chunks: list[str] = []
        async for token in self.llm.chat_stream(messages, RAG_TEMPERATURE):
            chunks.append(token)
        return "".join(chunks), hits

    async def stream_answer(self, question: str) -> AsyncIterator[str]:
        """Itère les tokens de la réponse (erreur exacte si short-circuit)."""
        _, prompt, bypass = await self.retrieve(question)
        if bypass:
            yield RAG_ERROR
            return
        messages = [ChatMessage(m["role"], m["content"])
                    for m in prompt.to_messages()]
        async for token in self.llm.chat_stream(messages, RAG_TEMPERATURE):
            yield token

    async def _suggest_title(self, question: str) -> str | None:
        """Nom de page proche du lexique de la question, ou None."""
        suggest = getattr(self.retriever, "suggest_title", None)
        if suggest is None:
            return None
        return await suggest(question)