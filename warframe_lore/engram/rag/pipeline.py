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

from .audit import audit_empty, audit_rejected, audit_retrieval
from .context import RAGContext
from .prompt.builder import PromptBuilder, RAGPrompt
from .query.aliases import AliasResolver
from .query.probes import detect_probe
from .query.query_guard import sanitize_query
from .query.search_query import search_query
from .retrieval.relevance import keep_relevant, missing_entity, relevance_floor
from .retrieval.retriever import DossierPage, RAGHit, Retriever

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
    # Narrative pagination: True when the subject's dossier still holds
    # passages beyond the page that was just read (the client may continue).
    story_more: bool = False


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
                  subject: str | None = None,
                  offset: int = 0,
                  exclude_ids: list[int] | None = None) -> Retrieval:
        """One retrieval, with its audit line (see the module docstring).

        ``subject`` opens a targeted story: the dossier is read story-first.
        ``exclude_ids`` is the ONLY pagination — the chunk ids the session
        already narrated, banned server-side (the client cursor is never
        trusted).  ``offset > 0`` merely marks a CONTINUATION: the semantic
        neighbours of the opening request are dropped so the part never
        re-anchors on the same salient facts.
        """
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
        story_more = False
        if subject:
            page = await self._dossier(subject, vector, exclude_ids)
            story_more = page.more
            if offset > 0:
                # Continuation: ONLY the next dossier page.  The semantic
                # neighbours are computed on the SAME query vector every part,
                # so re-merging them would re-anchor the model on the same
                # salient facts and echo the previous part (playtest: parts 2
                # and 3 near-identical).  An empty page = drained dossier.
                found = page.hits
            elif page.hits:
                found = self._merge_dedup(page.hits + found)
        floor = relevance_floor(self.suggestion_min_score,
                                self.critical_min_score)
        # The floor and the title suggestion target OFF-TOPIC neighbours of a
        # fresh question.  A continuation reads the subject's OWN page (story
        # reading order): the floor would drop late chapters that score low
        # against the opening request, and a suggestion would derail the part.
        kept = found if offset > 0 else keep_relevant(found, floor)
        suggestion = None
        if not kept:
            # Search too weak (absent topic, typo…): never ground a response on
            # off-topic neighbours — attempt a disambiguation, else bypass.
            if offset == 0:
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
        audit_retrieval(question, search, found, suggestion, bypass, prompt,
                        subject=subject, offset=offset)
        return Retrieval(hits=kept, prompt=prompt, bypass=bypass,
                         story_more=story_more)

    def _abstain(self, question: str, rejected: bool = False) -> Retrieval:
        """Empty input or hostile probe: a prompt with no passage, no LLM.

        A probe costs nothing: no embedding, no pgvector, no model, and the
        payload never enters the conversational memory.
        """
        prompt = self.prompt_builder.build(question, [], alias_note="",
                                           suggestion=None)
        prompt.rejected = rejected
        if rejected:
            audit_rejected(question)
        else:
            audit_empty(question, prompt)
        return Retrieval(hits=[], prompt=prompt, bypass=True)

    async def _suggest_title(self, question: str) -> str | None:
        """Page name close to the question's lexicon, or None."""
        suggest = getattr(self.retriever, "suggest_title", None)
        if suggest is None:
            return None
        return await suggest(question)

    async def _dossier(self, subject: str, vector: list[float],
                       exclude_ids: list[int] | None = None) -> DossierPage:
        method = getattr(self.retriever, "dossier", None)
        if method is None:
            return DossierPage(hits=[])
        # The dossier always pages from offset 0: the sub-retriever returns
        # the FIRST page of the still-unseen fragments — the session ban list
        # (``exclude_ids``) is the only cursor, so no client offset can force
        # a skip forward or loop back.
        return await method(subject, vector, offset=0, exclude_ids=exclude_ids)

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

__all__ = ["Retrieval", "RetrievalPipeline"]
