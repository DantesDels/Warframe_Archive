"""Document RAG service: the answer shapes on top of the retrieval pipeline.

High level: depends only on injected abstractions (``EmbeddingProvider``,
``Retriever``, ``LLMProvider``) — never on concrete storage or a concrete client
(D principle).  The retrieval decision (thresholds, guards, audit) lives in
:mod:`pipeline`; this module turns a :class:`Retrieval` into an answer: the
short-circuit strings, a full answer with its sources, or a token stream.

Short-circuit: without a trusted passage the LLM is NEVER called — the exact
:const:`RAG_ERROR` is returned (or :const:`JAILBREAK_REJECT` for a hostile
probe).  Formatting artifacts are stripped from the FINAL text only.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from ..models import ChatMessage
from .pipeline import RetrievalPipeline
from .prompt.builder import PromptBuilder, RAGPrompt
from .prompt.guards import CONFABULATION_ERROR, JAILBREAK_REJECT, RAG_ERROR
from .retrieval.retriever import RAGHit, Retriever
from .sanitize import strip_trailing_padding
from .verify import verify_answer_with_archive

if TYPE_CHECKING:
    from ..llm import EmbeddingProvider, LLMProvider
    from .context import RAGContext
    from .query.aliases import AliasResolver
    from .query.rewriter import QueryRewriter
    from .vocabulary import ArchiveVocabulary

# RAG inference temperature: 0.1 -> analytical/deterministic without blocking
# the engine (Gemma-2-9b-it Q4_K_M on 8 GB VRAM).
RAG_TEMPERATURE = 0.1


class RAGService:
    """Answer shapes (HTTP and WS) on top of one retrieval pipeline."""

    def __init__(self, embeddings: EmbeddingProvider, retriever: Retriever,
                 llm: LLMProvider, prompt_builder: PromptBuilder,
                 suggestion_min_score: float = 0.5,
                 critical_min_score: float | None = None,
                 query_rewriter: QueryRewriter | None = None,
                 alias_resolver: AliasResolver | None = None,
                 vocabulary: ArchiveVocabulary | None = None) -> None:
        self.llm = llm
        self.vocabulary = vocabulary
        self.pipeline = RetrievalPipeline(
            embeddings, retriever, prompt_builder,
            suggestion_min_score=suggestion_min_score,
            critical_min_score=critical_min_score,
            query_rewriter=query_rewriter,
            alias_resolver=alias_resolver)

    @property
    def prompt_builder(self) -> PromptBuilder:
        """Prompt assembler (the inspector reuses it for its debug payload)."""
        return self.pipeline.prompt_builder

    @property
    def alias_resolver(self) -> AliasResolver:
        """Alias middleware (shared with the hybrid search of the inspector)."""
        return self.pipeline.alias_resolver

    async def retrieve(self, question: str,
                       context: RAGContext | None = None, *,
                       subject: str | None = None
                       ) -> tuple[list[RAGHit], RAGPrompt, bool]:
        """Kept passages, assembled prompt and short-circuit flag.

        ``bypass`` signals the absence of a trusted passage AND of a
        disambiguation clue: the LLM must not be called.
        """
        outcome = await self.pipeline.run(question, context, subject=subject)
        return outcome.hits, outcome.prompt, outcome.bypass

    async def resolve(self, question: str,
                      context: RAGContext | None = None, *,
                      subject: str | None = None
                      ) -> tuple[str | None, str | None]:
        """Context/suggestion for a Roleplay turn (WS).

        ``bypass`` -> ``(None, None)``: the WS client then short-circuits with
        the exact error string.  Otherwise the context is safe (never an empty
        marker) and a non-null ``suggestion`` means disambiguation.
        """
        _, prompt, bypass = await self.retrieve(question, context=context,
                                                subject=subject)
        if bypass:
            return None, None
        return prompt.context, prompt.suggestion

    async def answer_with_sources(self, question: str,
                                  context: RAGContext | None = None
                                  ) -> tuple[str, list[RAGHit]]:
        """Model answer + relevant passages (short-circuit otherwise).

        The generated answer passes the deterministic entity gate
        (:mod:`.verify`) before being served: named entities absent from the
        retrieved ``<archives>`` are confabulations and trigger the abstention
        chain instead.
        """
        hits, prompt, bypass = await self.retrieve(question, context=context)
        short = self._short_circuit(prompt, bypass)
        if short is not None:
            return short, []
        chunks: list[str] = []
        async for token in self.llm.chat_stream(self._messages(prompt),
                                                RAG_TEMPERATURE):
            chunks.append(token)
        answer = strip_trailing_padding("".join(chunks))
        ok, _ = await verify_answer_with_archive(
            answer, prompt.context, self.vocabulary)
        return (answer if ok else CONFABULATION_ERROR), hits

    async def stream_answer(self, question: str,
                            context: RAGContext | None = None
                            ) -> AsyncIterator[str]:
        """Buffers, verifies and yields the answer (exact error if short-circuit).

        Same entity gate as :meth:`answer_with_sources`: the full response is
        assembled first, checked against the retrieved ``<archives>``, then
        emitted — streamed tokens cannot be recalled once sent.
        """
        _, prompt, bypass = await self.retrieve(question, context=context)
        short = self._short_circuit(prompt, bypass)
        if short is not None:
            yield short
            return
        chunks: list[str] = []
        async for token in self.llm.chat_stream(self._messages(prompt),
                                                RAG_TEMPERATURE):
            chunks.append(token)
        answer = "".join(chunks)
        ok, _ = await verify_answer_with_archive(
            answer, prompt.context, self.vocabulary)
        yield answer if ok else CONFABULATION_ERROR

    @staticmethod
    def _short_circuit(prompt: RAGPrompt, bypass: bool) -> str | None:
        """Exact rejection string when the model must not be called."""
        if prompt.rejected:
            return JAILBREAK_REJECT
        return RAG_ERROR if bypass else None

    @staticmethod
    def _messages(prompt: RAGPrompt) -> list[ChatMessage]:
        """Chat messages of the prompt (one tagged system + the question)."""
        return [ChatMessage(item["role"], item["content"])
                for item in prompt.to_messages()]


__all__ = ["RAG_TEMPERATURE", "RAGService"]
