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
"""

from __future__ import annotations

import logging
import re
from collections.abc import AsyncIterator

from ..llm import EmbeddingProvider, LLMProvider
from ..models import ChatMessage
from .aliases import AliasResolver
from .context import RAGContext
from .probes import detect_probe
from .prompt import (JAILBREAK_REJECT, NO_DATA_MARKER, PromptBuilder, RAG_ERROR,
                     RAGPrompt)
from .retriever import RAGHit, Retriever
from .rewriter import QueryRewriter
from .sanitize import strip_trailing_padding

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

# Entity-lookup questions ("qui est X", "qu'est-ce que X", "parle-moi de X",
# "que sais-tu de X", "c'est qui X"…).  When the named target never appears
# in the retrieved passages, the model would otherwise invent a biography
# (playtest: "Qui est Vena ?" → hallucinated Warframe).  The guard below
# short-circuits those before the LLM is ever called.
_LOOKUP_PREFIXES = (
    "qui est ", "qui était ", "qui es-tu ",
    "qu'est-ce que ", "qu'est-ce qu'",
    "c'est qui ", "c'est quoi ",
    "parle-moi de ", "parlez-moi de ",
    "parle-moi d'", "parlez-moi d'",
    "que sais-tu de ", "que sais-tu sur ",
    "que peux-tu me dire de ", "que peux-tu me dire sur ",
    "raconte-moi ", "racontez-moi ",
)

# Leading articles/determiners skipped before the proper-noun detection.
_DETERMINERS = frozenset({
    "le", "la", "les", "un", "une", "des", "du", "de", "ce", "cet", "cette",
    "ces", "mon", "ma", "mes", "son", "sa", "ses", "ton", "ta", "tes",
    "notre", "votre", "leur", "leurs", "au", "aux",
})

# French elisions stripped before the proper-noun detection ("l'Orokin" →
# "Orokin", "d'Arthur" → "Arthur").
_ELISION_PREFIXES = ("l'", "d'", "s'", "n'", "j'", "t'", "m'", "qu'")


def _first_proper_noun(tail: str) -> str | None:
    """First significant token of the tail, returned only if it is a
    capitalised proper noun; a lowercase descriptor ("le fondateur des…")
    yields ``None`` so a paraphrasing answer is never false-positived."""
    for token in tail.split():
        word = token.strip("'’\"“”()[]-.,;:!?")
        low = word.lower()
        if low.startswith(_ELISION_PREFIXES):
            word = word[2:]
            low = word.lower()
        if len(word) < 3 or low in _DETERMINERS:
            continue
        return word if word[0].isupper() else None
    return None


def _lookup_entity(question: str) -> str | None:
    """Proper-noun target of a "who/what is X" lookup, else ``None``."""
    q = (question or "").strip()
    low = q.lower()
    for prefix in _LOOKUP_PREFIXES:
        if low.startswith(prefix):
            tail = q[len(prefix):].strip().rstrip("?.!…")
            return _first_proper_noun(tail)
    return None


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
        note = " search_q=%r" % (search_question,) if search_question != question else ""
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