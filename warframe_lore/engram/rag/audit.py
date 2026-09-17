"""Audit lines of one retrieval (missing data never looks like disobedience).

Single responsibility: the INFO/WARNING lines that tell apart a passage missing
from the corpus (ETL, absent page, typo) from a model ignoring the archives it
was given.  Kept out of :mod:`pipeline` so the retrieval flow reads as the
sequence of decisions it is — and so every audit line is written once.
"""

from __future__ import annotations

import logging

from .prompt.builder import RAGPrompt
from .retrieval.retriever import RAGHit

log = logging.getLogger("warframe_lore.engram.rag")

# Characters of context echoed in the audit line: enough to recognise the
# passage family, short enough to keep one retrieval on one log line.
CONTEXT_PREVIEW = 180


def audit_retrieval(question: str, search: str, found: list[RAGHit],
                    suggestion: str | None, bypass: bool, prompt: RAGPrompt, *,
                    subject: str | None = None, offset: int = 0) -> None:
    """One INFO line per retrieval: the whole decision stays auditable."""
    note = f" search_q={search!r}" if search != question else ""
    if subject:
        note += f" dossier={subject!r} offset={offset}"
    log.info("Audit RAG question=%r%s hit=%d suggestion=%r bypass=%s "
             "ctx_car=%d ctx=%r...", question, note, len(found), suggestion,
             bypass, len(prompt.context),
             prompt.context[:CONTEXT_PREVIEW].replace("\n", " "))


def audit_rejected(question: str) -> None:
    """A hostile probe: a WARNING, so the scan shows up in the logs."""
    log.warning("Audit RAG question=%r SONDE_HOSTILE bypass=True "
                "rejected=True (aucun appel modèle)", question)


def audit_empty(question: str, prompt: RAGPrompt) -> None:
    """Empty input: an INFO line, so the absence of a call explains itself."""
    log.info("Audit RAG question=%r hit=0 suggestion=None bypass=True "
             "ctx_car=%d ctx=%r...", question, len(prompt.context),
             prompt.context[:CONTEXT_PREVIEW].replace("\n", " "))


__all__ = ["CONTEXT_PREVIEW", "audit_empty", "audit_rejected", "audit_retrieval"]
