"""Document RAG service: embedding -> retrieval -> prompt -> LLM.

High level: depends only on injected abstractions (``EmbeddingProvider``,
``Retriever``, ``LLMProvider``) — never on concrete storage or a concrete
client (D principle). The data access point lives behind :class:`Retriever`.
Audit: each request logs the context extracted from pgvector before sending
to the LLM, to isolate missing data (ETL) from model disobedience.
Short-circuit: without a trusted passage, the LLM is never called — the
exact string :const:`RAG_ERROR` is returned directly.

State isolation: the service is STATELESS regarding conversational memory.
Anaphora enrichment reads/writes a caller-owned :class:`RAGContext`
(request-scoped via ``Depends``, or per WebSocket connection) — no global
``_last_query``, no persistent dictionary on the singleton, so nothing
survives a request or a connection.

Query sanitisation and the entity-lookup guard live in
:mod:`warframe_lore.engram.rag.query_guard`; the error/guard chains in
:mod:`warframe_lore.engram.rag.guards`.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from ..llm import EmbeddingProvider, LLMProvider
from ..models import ChatMessage
from .aliases import AliasResolver
from .context import RAGContext
from .guards import JAILBREAK_REJECT, RAG_ERROR
from .probes import detect_probe
from .prompt import PromptBuilder, RAGPrompt
from .query_guard import _is_anaphoric, _lookup_entity, sanitize_query
from .retriever import RAGHit, Retriever
from .rewriter import QueryRewriter
from .sanitize import strip_trailing_padding

log = logging.getLogger("warframe_lore.engram.rag")

# RAG inference temperature: 0.1 -> analytical/deterministic without
# blocking the engine (Gemma-2-9b-it Q4_K_M on 8 GB VRAM).
RAG_TEMPERATURE = 0.1


class RAGService:
    """Orchestrates an end-to-end document RAG query (stateless concern)."""

    def __init__(self, embeddings: EmbeddingProvider, retriever: Retriever,
                 llm: LLMProvider, prompt_builder: PromptBuilder,
                 suggestion_min_score: float = 0.5,
                 critical_min_score: float | None = None,
                 query_rewriter: QueryRewriter | None = None,
                 alias_resolver: AliasResolver | None = None) -> None:
        self.embeddings = embeddings
        self.retriever = retriever
        self.llm = llm
        self.prompt_builder = prompt_builder
        self.suggestion_min_score = suggestion_min_score
        # Critical response threshold: below this score (typo, out-of-corpus
        # topic), the LLM is NEVER called with a weak passage. Calibrated on
        # real corpus (Lettie 0.55-0.63, Orokin 0.59-0.61, Albrecht 0.52-0.53).
        # Default: identical to the disambiguation threshold.
        self.critical_min_score = critical_min_score
        # Search-query rewriting (anaphora resolution). The rewriter is
        # STATELESS: the per-user window lives in the RAGContext supplied by
        # the caller, never on this singleton.
        self.query_rewriter = query_rewriter
        # Alias middleware: nickname -> canonical name, applied to the raw
        # query BEFORE vectorization (alias expansion actually reaches the
        # embedding; a bare nickname would not).
        self.alias_resolver = alias_resolver or AliasResolver()

    async def retrieve(self, question: str,
                       context: RAGContext | None = None
                       ) -> tuple[list[RAGHit], RAGPrompt, bool]:
        """Assembles the prompt and decides on short-circuit, with logging.

        The query is first enriched by the alias middleware (nickname ->
        canonical name) — the EXPANDED text is the one embedded, so the
        canonical name actually reaches pgvector. ``bypass`` signals the
        absence of a trusted passage AND disambiguation: the LLM must not be
        called (short-circuit). Anaphoric questions ("...this story mentioned
        earlier?") are rewritten into a standalone SEARCH query using the
        caller-owned ``context``; the model only ever sees the user's
        original wording.
        """
        question = sanitize_query(question)
        if not question:
            # Empty/non-significant input: immediate abstention → the LLM
            # is never called.
            prompt = self.prompt_builder.build("", [], alias_note="",
                                               suggestion=None)
            log.info("Audit RAG question=%r hit=0 suggestion=None bypass=True "
                     "ctx_car=%d ctx=%r...", question, len(prompt.context),
                     prompt.context[:180].replace("\n", " "))
            return [], prompt, True
        if detect_probe(question):
            # Hostile probe (SQL injection, privilege escalation, third-party
            # mention): DETERMINISTIC rejection, no embedding, no pgvector, no
            # LLM. The same payload incurs zero cost and never enters the
            # context memory.
            prompt = self.prompt_builder.build(question, [], alias_note="",
                                               suggestion=None)
            prompt.rejected = True
            log.warning("Audit RAG question=%r SONDE_HOSTILE bypass=True "
                        "rejected=True (aucun appel modèle)", question)
            return [], prompt, True
        expanded, alias_note, canon = self.alias_resolver.resolve(question)
        # Search query: alias-expanded, then rewritten when anaphoric
        # (micro LLM call or concatenation, within the caller-owned context).
        context = context or RAGContext()
        search_question = await self._rewrite_for_search(expanded, context)
        query_vector = (await self.embeddings.embed([search_question]))[0]
        hits = await self.retriever.search(query_vector)
        floor = (self.suggestion_min_score if self.critical_min_score is None
                 else max(self.critical_min_score, self.suggestion_min_score))
        # Relevance threshold: no passage below ``floor`` (e.g. typos,
        # out-of-corpus topics) must reach the LLM. We filter first, so
        # ``top`` reflects the strength of the best retained passage.
        used_hits = [h for h in hits if h.score >= floor]
        top = used_hits[0].score if used_hits else 0.0
        suggestion = None
        if top < floor:
            # Search too weak (absent topic, typo...): never ground a
            # response on off-topic neighbors. Context is CLEARED;
            # disambiguation is attempted (canonical alias or neighboring
            # title), otherwise short-circuit without ever calling the LLM.
            suggestion = (canon if alias_note
                          else await self._suggest_title(question))
            # Context stripped of content: no off-topic neighbor to the LLM.
            used_hits = []
        bypass = not used_hits and suggestion is None
        # Entity-lookup guard (playtest "Qui est Vena ?"): a "qui est X"
        # question whose named target NEVER appears in the retrieved passages
        # must not reach the model — the archives cannot support an answer, so
        # short-circuit instead of letting the model invent a biography.
        if not bypass and used_hits:
            entity = _lookup_entity(question)
            context_blob = " ".join(h.content for h in used_hits).lower()
            if entity and entity.lower() not in context_blob:
                used_hits = []
                suggestion = None
                bypass = True
                log.info("Audit RAG entity=%r absent des passages -> "
                         "court-circuit (anti-hallucination)", entity)
        # The anti-vide (empty-context) truncation works below the RAG route,
        # whatever the search query was: the PROMPT always embeds the user's
        # exact wording.
        prompt = self.prompt_builder.build(
            question, used_hits, alias_note=alias_note, suggestion=suggestion)
        note = ""
        if search_question != question:
            note = f" search_q={search_question!r}"
        log.info("Audit RAG question=%r%s hit=%d suggestion=%r bypass=%s "
                 "ctx_car=%d ctx=%r...",
                 question, note, len(hits), suggestion, bypass,
                 len(prompt.context), prompt.context[:180].replace("\n", " "))
        return used_hits, prompt, bypass

    async def _rewrite_for_search(self, question: str,
                                  context: RAGContext) -> str:
        """Search query for embedding: alias-expanded, rewritten when
        anaphoric using the caller-owned context.

        With a per-user rewriter: anaphoric questions are reformulated
        (micro LLM call, concatenation fallback); plain questions are
        remembered in ``context``. Without one, the last established
        question in ``context`` is concatenated. The context is created by
        the caller (HTTP request / WS connection) — the shared service keeps
        no memory of its own.
        """
        if self.query_rewriter is not None:
            return await self.query_rewriter.rewrite(
                context, question, _is_anaphoric(question))
        if _is_anaphoric(question) and context.last_question:
            return f"{context.last_question} {question}"
        context.remember(question)
        return question

    async def resolve(self, question: str,
                      context: RAGContext | None = None
                      ) -> tuple[str | None, str | None]:
        """Context/suggestion for a Roleplay turn (WS).

        ``bypass`` -> ``(None, None)``: the WS client must then short-circuit
        with the exact error string. Otherwise ``(context, suggestion)``: the
        context is safe (never an empty marker); a non-null ``suggestion``
        indicates to the router that it concerns disambiguation.
        """
        _, prompt, bypass = await self.retrieve(question, context=context)
        if bypass:
            return None, None
        return prompt.context, prompt.suggestion

    async def answer_with_sources(self, question: str,
                                  context: RAGContext | None = None
                                  ) -> tuple[str, list[RAGHit]]:
        """Model answer + relevant passages (short-circuit otherwise)."""
        hits, prompt, bypass = await self.retrieve(question, context=context)
        if prompt.rejected:
            return JAILBREAK_REJECT, []
        if bypass:
            return RAG_ERROR, []
        messages = [ChatMessage(m["role"], m["content"])
                    for m in prompt.to_messages()]
        chunks: list[str] = []
        async for token in self.llm.chat_stream(messages, RAG_TEMPERATURE):
            chunks.append(token)
        # Formatting-artifact sanitization (lone trailing ``*`` / ``-`` /
        # whitespace): applied to the FINAL concatenation only.
        return strip_trailing_padding("".join(chunks)), hits

    async def stream_answer(self, question: str,
                            context: RAGContext | None = None
                            ) -> AsyncIterator[str]:
        """Iterates over response tokens (exact error if short-circuit)."""
        _, prompt, bypass = await self.retrieve(question, context=context)
        if prompt.rejected:
            yield JAILBREAK_REJECT
            return
        if bypass:
            yield RAG_ERROR
            return
        messages = [ChatMessage(m["role"], m["content"])
                    for m in prompt.to_messages()]
        async for token in self.llm.chat_stream(messages, RAG_TEMPERATURE):
            yield token

    async def _suggest_title(self, question: str) -> str | None:
        """Page name close to the question's lexicon, or None."""
        suggest = getattr(self.retriever, "suggest_title", None)
        if suggest is None:
            return None
        return await suggest(question)
