"""Document RAG service: embedding -> retrieval -> prompt -> LLM.

High level: depends only on injected abstractions (``EmbeddingProvider``,
``Retriever``, ``LLMProvider``) — never on concrete storage or a concrete
client (D principle). The data access point lives behind :class:`Retriever`.
Audit: each request logs the context extracted from pgvector before sending
to the LLM, to isolate missing data (ETL) from model disobedience.
Short-circuit: without a trusted passage, the LLM is never called — the
exact string :const:`RAG_ERROR` is returned directly.
"""

from __future__ import annotations

import logging
import re
from collections.abc import AsyncIterator

from ..llm import EmbeddingProvider, LLMProvider
from ..models import ChatMessage
from .aliases import resolve_alias
from .probes import detect_probe
from .prompt import (JAILBREAK_REJECT, NO_DATA_MARKER, PromptBuilder, RAG_ERROR,
                     RAGPrompt)
from .retriever import RAGHit, Retriever

log = logging.getLogger("warframe_lore.engram.rag")

# RAG inference temperature: 0.1 -> analytical/deterministic without
# blocking the engine (Gemma-2-9b-it Q4_K_M on 8 GB VRAM).
RAG_TEMPERATURE = 0.1

# Anaphoric markers: a question referring to the previous message
# ("...that PS5 story mentioned earlier?") retrieves poorly in vector
# because it names no entity. The last query is then reused to enrich
# the SEARCH (never the text seen by the model, which remains the
# user's message).
_ANAPHORIC = re.compile(
    r"^(et\s+|d'ailleurs\s+)?(cette\b|cet\b|cette histoire\b|cette chose\b|"
    r"ce sujet\b|celui[- ]ci|celui[- ]là|celles?[- ]ci|celles?[- ]là|"
    r"il\b|elle\b|ils\b|elles\b|ça\b|cela\b)",
    re.IGNORECASE)

_ANAPHORIC_MARKERS = (
    "juste avant", "cette histoire", "cette chose", "ce sujet",
    "parlé de", "dit juste", "comme je disais", "comme tu disais",
)

# Control characters (outside legitimate tab/newline after split):
# no control injection in embeddings nor in logs.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

_MAX_QUERY_LEN = 2000

# Discord tokens (@user, #channel, custom emojis): neutralized upstream
# so that no snowflake is ever reflected by the LLM in its response
# (anti echo-ping of a third-party user).
_MENTION_TOKENS = re.compile(r"<@!?\d+>|<#\d+>|<a?:[a-z0-9_]+:\d+>",
                             re.IGNORECASE)


def sanitize_query(text: str) -> str:
    """Sanitizes user input before search/vectorization: strips control
    characters, normalizes whitespace and caps length. Discord mentions
    are replaced with a neutral label. Serves NO SQL interpolation — all
    queries go through parameterized SQLAlchemy (anti-SQLi by construction).
    """
    cleaned = _CONTROL_CHARS.sub(" ", str(text))
    cleaned = _MENTION_TOKENS.sub("un utilisateur", cleaned)
    return " ".join(cleaned.split())[:_MAX_QUERY_LEN]


def _is_anaphoric(question: str) -> bool:
    """True if the question points to the previous message without an entity."""
    q = question.strip().lower()
    if not q or len(q) > 120:
        return False
    if any(marker in q for marker in _ANAPHORIC_MARKERS):
        return True
    return bool(_ANAPHORIC.match(q))


class RAGService:
    """Orchestrates an end-to-end document RAG query."""

    def __init__(self, embeddings: EmbeddingProvider, retriever: Retriever,
                 llm: LLMProvider, prompt_builder: PromptBuilder,
                 suggestion_min_score: float = 0.5,
                 critical_min_score: float | None = None) -> None:
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
        self._last_query: str | None = None

    async def retrieve(self, question: str
                       ) -> tuple[list[RAGHit], RAGPrompt, bool]:
        """Assembles the prompt and decides on short-circuit, with logging.

        The query is first enriched by ``resolve_alias`` (nickname -> canonical
        name) to make embedding more reliable. ``bypass`` signals the absence
        of a trusted passage AND disambiguation: the LLM must not be called
        (short-circuit).
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
            # LLM. The same payload incurs zero cost and never enters query
            # memory.
            prompt = self.prompt_builder.build(question, [], alias_note="",
                                               suggestion=None)
            prompt.rejected = True
            log.warning("Audit RAG question=%r SONDE_HOSTILE bypass=True "
                        "rejected=True (aucun appel modèle)", question)
            return [], prompt, True
        expanded, alias_note, canon = resolve_alias(question)
        # Query memory: an anaphoric question ("that story... mentioned
        # earlier?") names no entity → the last question is reused to enrich
        # vector search only.
        search_question = question
        if self._last_query and _is_anaphoric(question):
            search_question = f"{self._last_query} {question}"
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
        if not bypass:
            # Truly established topic: sole legitimate enrichment basis for
            # a future anaphoric question. A short-circuited query (bypass)
            # memorizes NOTHING — otherwise the absent topic would pollute the
            # next one ("that story..." resuming "green mouse").
            self._last_query = question
        prompt = self.prompt_builder.build(
            question, used_hits, alias_note=alias_note, suggestion=suggestion)
        note = " search_q=%r" % (search_question,) if search_question != question else ""
        log.info("Audit RAG question=%r%s hit=%d suggestion=%r bypass=%s "
                 "ctx_car=%d ctx=%r...",
                 question, note, len(hits), suggestion, bypass,
                 len(prompt.context), prompt.context[:180].replace("\n", " "))
        return used_hits, prompt, bypass

    async def resolve(self, question: str
                      ) -> tuple[str | None, str | None]:
        """Context/suggestion for a Roleplay turn (WS).

        ``bypass`` -> ``(None, None)``: the WS client must then short-circuit
        with the exact error string. Otherwise ``(context, suggestion)``: the
        context is safe (never an empty marker); a non-null ``suggestion``
        indicates to the router that it concerns disambiguation.
        """
        _, prompt, bypass = await self.retrieve(question)
        if bypass:
            return None, None
        return prompt.context, prompt.suggestion

    async def answer_with_sources(self, question: str
                                  ) -> tuple[str, list[RAGHit]]:
        """Model answer + relevant passages (short-circuit otherwise)."""
        hits, prompt, bypass = await self.retrieve(question)
        if prompt.rejected:
            return JAILBREAK_REJECT, []
        if bypass:
            return RAG_ERROR, []
        messages = [ChatMessage(m["role"], m["content"])
                    for m in prompt.to_messages()]
        chunks: list[str] = []
        async for token in self.llm.chat_stream(messages, RAG_TEMPERATURE):
            chunks.append(token)
        return "".join(chunks), hits

    async def stream_answer(self, question: str) -> AsyncIterator[str]:
        """Iterates over response tokens (exact error if short-circuit)."""
        _, prompt, bypass = await self.retrieve(question)
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