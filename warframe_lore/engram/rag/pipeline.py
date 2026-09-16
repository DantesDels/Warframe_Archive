"""Retrieval pipeline: from the raw question to the decided RAG prompt.

Single responsibility: run ONE retrieval — sanitisation, hostile probe, alias
expansion, search-query preparation, embedding, vector search, relevance guards,
prompt assembly — and audit it.  The LLM is never called here: the answer shapes
live in :mod:`service`.

Stateless: the anaphora memory is the caller-owned :class:`RAGContext` (per HTTP
request or per WebSocket connection), never an attribute of this object.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .context import RAGContext
from .prompt.builder import PromptBuilder, RAGPrompt
from .query.aliases import AliasResolver
from .query.probes import detect_probe
from .query.query_guard import sanitize_query
from .query.search_query import search_query
from .retrieval.relevance import keep_relevant, missing_entity, relevance_floor
from .retrieval.retriever import RAGHit, Retriever

if TYPE_CHECKING:
    from ..llm import EmbeddingProvider
    from .query.rewriter import QueryRewriter

log = logging.getLogger("warframe_lore.engram.rag")


@dataclass(frozen=True)
class Retrieval:
    """Outcome of one retrieval: kept passages, prompt, short-circuit flag."""

    hits: list[RAGHit]
    prompt: RAGPrompt
    bypass: bool


class RetrievalPipeline:
    """sanitise -> probe -> aliases -> embed -> search -> guards -> prompt."""

    def __init__(self, embeddings: EmbeddingProvider, retriever: Retriever,
                 prompt_builder: PromptBuilder,
                 suggestion_min_score: float = 0.5,
                 critical_min_score: float | None = None,
                 query_rewriter: QueryRewriter | None = None,
                 alias_resolver: AliasResolver | None = None) -> None:
        self.embeddings = embeddings
        self.retriever = retriever
        self.prompt_builder = prompt_builder
        self.suggestion_min_score = suggestion_min_score
        # Critical threshold: below it (typo, out-of-corpus topic) the LLM is
        # NEVER called with a weak passage.  Calibrated on the real corpus
        # (Lettie 0.55-0.63, Orokin 0.59-0.61, Albrecht 0.52-0.53).
        self.critical_min_score = critical_min_score
        self.query_rewriter = query_rewriter
        # Alias middleware: nickname -> canonical name, applied BEFORE the
        # embedding so the expansion actually reaches pgvector.
        self.alias_resolver = alias_resolver or AliasResolver()

    async def run(self, question: str,
                  context: RAGContext | None = None, *,
                  subject: str | None = None) -> Retrieval:
        """One retrieval, with its audit line (see the module docstring)."""
        question = sanitize_query(question)
        if not question:
            return self._abstain(question)          # empty input: no LLM
        if detect_probe(question):
            return self._abstain(question, rejected=True)
        expanded, alias_note, canon = self.alias_resolver.resolve(question)
        search = await search_query(expanded, context or RAGContext(),
                                    self.query_rewriter)
        vector = (await self.embeddings.embed([search]))[0]
        found = await self.retriever.search(vector)
        if subject:
            dossier = await self._dossier(subject, vector)
            if dossier:
                found = self._merge_dedup(dossier + found)
        floor = relevance_floor(self.suggestion_min_score,
                                self.critical_min_score)
        kept = keep_relevant(found, floor)
        suggestion = None
        if not kept:
            # Search too weak (absent topic, typo…): never ground a response on
            # off-topic neighbours — attempt a disambiguation, else bypass.
            suggestion = (canon if alias_note
                          else await self._suggest_title(question))
        entity = missing_entity(question, kept)
        if entity:
            kept, suggestion = [], None
            log.info("Audit RAG entity=%r absent des passages -> "
                     "court-circuit (anti-hallucination)", entity)
        prompt = self.prompt_builder.build(question, kept, alias_note=alias_note,
                                           suggestion=suggestion)
        bypass = not kept and suggestion is None
        self._audit(question, search, found, suggestion, bypass, prompt,
                    subject=subject)
        return Retrieval(hits=kept, prompt=prompt, bypass=bypass)

    def _abstain(self, question: str, rejected: bool = False) -> Retrieval:
        """Empty input or hostile probe: a prompt with no passage, no LLM.

        A probe costs nothing: no embedding, no pgvector, no model, and the
        payload never enters the conversational memory.
        """
        prompt = self.prompt_builder.build(question, [], alias_note="",
                                           suggestion=None)
        prompt.rejected = rejected
        if rejected:
            log.warning("Audit RAG question=%r SONDE_HOSTILE bypass=True "
                        "rejected=True (aucun appel modèle)", question)
        else:
            log.info("Audit RAG question=%r hit=0 suggestion=None bypass=True "
                     "ctx_car=%d ctx=%r...", question, len(prompt.context),
                     prompt.context[:180].replace("\n", " "))
        return Retrieval(hits=[], prompt=prompt, bypass=True)

    async def _suggest_title(self, question: str) -> str | None:
        """Page name close to the question's lexicon, or None."""
        suggest = getattr(self.retriever, "suggest_title", None)
        if suggest is None:
            return None
        return await suggest(question)

    async def _dossier(self, subject: str,
                       vector: list[float]) -> list[RAGHit]:
        """Subject-page passages for a targeted story (``[]`` if unsupported)."""
        method = getattr(self.retriever, "dossier", None)
        if method is None:
            return []
        return await method(subject, vector)

    @staticmethod
    def _merge_dedup(hits: list[RAGHit]) -> list[RAGHit]:
        """Dedup by passage identity; first occurrence wins (dossier first)."""
        seen: set[tuple[str, str]] = set()
        merged: list[RAGHit] = []
        for hit in hits:
            key = (hit.page_title, hit.content)
            if key not in seen:
                seen.add(key)
                merged.append(hit)
        return merged

    @staticmethod
    def _audit(question: str, search: str, found: list[RAGHit],
               suggestion: str | None, bypass: bool,
               prompt: RAGPrompt, *,
               subject: str | None = None) -> None:
        """One INFO line per retrieval: isolates missing data (ETL) from model
        disobedience."""
        note = f" search_q={search!r}" if search != question else ""
        if subject:
            note += f" dossier={subject!r}"
        log.info("Audit RAG question=%r%s hit=%d suggestion=%r bypass=%s "
                 "ctx_car=%d ctx=%r...", question, note, len(found),
                 suggestion, bypass, len(prompt.context),
                 prompt.context[:180].replace("\n", " "))


__all__ = ["Retrieval", "RetrievalPipeline"]
