"""Service RAG documentaire : embedding -> récupération -> prompt -> LLM.

Haut niveau : ne dépend que d'abstractions injectées (``EmbeddingProvider``,
``Retriever``, ``LLMProvider``) — jamais d'un stockage ou d'un client concret
(principe D).  Le point d'accès aux données vit derrière :class:`Retriever`.
Audit : chaque requête journalise le contexte extrait de pgvector avant son
envoi au LLM, pour isoler un manque de données (ETL) d'une désobéissance
du modèle.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from ..llm import EmbeddingProvider, LLMProvider
from ..models import ChatMessage
from .prompt import PromptBuilder, RAGPrompt
from .retriever import RAGHit, Retriever

log = logging.getLogger("warframe_lore.engram.rag")


class RAGService:
    """Orchestre une requête RAG documentaire de bout en bout."""

    def __init__(self, embeddings: EmbeddingProvider, retriever: Retriever,
                 llm: LLMProvider, prompt_builder: PromptBuilder) -> None:
        self.embeddings = embeddings
        self.retriever = retriever
        self.llm = llm
        self.prompt_builder = prompt_builder

    async def _build_prompt(self, question: str) -> tuple[list[RAGHit], RAGPrompt]:
        """Récupère les passages et assemble le prompt, avec journalisation."""
        query_vector = (await self.embeddings.embed([question]))[0]
        hits = await self.retriever.search(query_vector)
        prompt = self.prompt_builder.build(question, hits)
        log.info("Audit RAG question=%r hit=%d ctx_car=%d ctx=%r...",
                 question, len(hits), len(prompt.context),
                 prompt.context[:180].replace("\n", " "))
        return hits, prompt

    async def answer(self, question: str) -> str:
        """Retourne la réponse complète du modèle (sans sources)."""
        answer, _ = await self.answer_with_sources(question)
        return answer

    async def answer_with_sources(self, question: str
                                  ) -> tuple[str, list[RAGHit]]:
        """Réponse du modèle + passages pertinents ayant servi de contexte."""
        hits, prompt = await self._build_prompt(question)
        messages = [ChatMessage(m["role"], m["content"])
                    for m in prompt.to_messages()]
        chunks: list[str] = []
        async for token in self.llm.chat_stream(messages):
            chunks.append(token)
        return "".join(chunks), hits

    async def stream_answer(self, question: str) -> AsyncIterator[str]:
        """Itère les tokens de la réponse, générée depuis le contexte RAG."""
        hits, prompt = await self._build_prompt(question)
        messages = [ChatMessage(m["role"], m["content"])
                    for m in prompt.to_messages()]
        async for token in self.llm.chat_stream(messages):
            yield token