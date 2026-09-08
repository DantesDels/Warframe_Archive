"""Service RAG documentaire : embedding -> récupération -> prompt -> LLM.

Haut niveau : ne dépend que d'abstractions injectées (``EmbeddingProvider``,
``Retriever``, ``LLMProvider``) — jamais d'un stockage ou d'un client concret
(principe D).  Le point d'accès aux données vit derrière :class:`Retriever`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from ..llm import EmbeddingProvider, LLMProvider
from ..models import ChatMessage
from .prompt import PromptBuilder
from .retriever import RAGHit, Retriever


class RAGService:
    """Orchestre une requête RAG documentaire de bout en bout."""

    def __init__(self, embeddings: EmbeddingProvider, retriever: Retriever,
                 llm: LLMProvider, prompt_builder: PromptBuilder) -> None:
        self.embeddings = embeddings
        self.retriever = retriever
        self.llm = llm
        self.prompt_builder = prompt_builder

    async def answer(self, question: str) -> str:
        """Retourne la réponse complète du modèle (sans sources)."""
        answer, _ = await self.answer_with_sources(question)
        return answer

    async def answer_with_sources(self, question: str
                                  ) -> tuple[str, list[RAGHit]]:
        """Réponse du modèle + passages pertinents ayant servi de contexte."""
        hits = await self.retriever.search(
            (await self.embeddings.embed([question]))[0])
        prompt = self.prompt_builder.build(question, hits)
        messages = [ChatMessage(m["role"], m["content"])
                    for m in prompt.to_messages()]
        chunks: list[str] = []
        async for token in self.llm.chat_stream(messages):
            chunks.append(token)
        return "".join(chunks), hits

    async def stream_answer(self, question: str) -> AsyncIterator[str]:
        """Itère les tokens de la réponse, générée depuis le contexte RAG."""
        hits = await self.retriever.search(
            (await self.embeddings.embed([question]))[0])
        prompt = self.prompt_builder.build(question, hits)
        messages = [ChatMessage(m["role"], m["content"])
                    for m in prompt.to_messages()]
        async for token in self.llm.chat_stream(messages):
            yield token