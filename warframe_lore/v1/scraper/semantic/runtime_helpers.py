"""Blob hydration and budget-aware LLM adapter helpers for semantic pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..adapters.outbound.llm.openai_compat import OpenAiCompatLlmAdapter
from ..capabilities.models import LlmBudget, UniverseCapabilities
from ..ports.outbound.llm import LlmPort


def hydrate_doc(doc: dict[str, Any], blob_root: Path | None) -> dict[str, Any]:
    """Load full offloaded text from blobs/<blobRef> when available."""
    blob_ref = str(doc.get("blobRef") or "").strip()
    if not blob_ref or blob_root is None:
        return doc
    blob_path = blob_root / "blobs" / blob_ref
    if not blob_path.is_file():
        return doc
    try:
        full_text = blob_path.read_text(encoding="utf-8")
    except OSError:
        return doc
    if len(full_text) <= len(str(doc.get("content") or "")):
        return doc
    clone = dict(doc)
    clone["content"] = full_text
    return clone


def resolve_llm_adapter(
    budget: LlmBudget | dict[str, Any] | None,
    explicit: LlmPort | None,
) -> LlmPort | None:
    """Return explicit adapter or build one when GraphRAG LLM budget is enabled."""
    if explicit is not None:
        return explicit
    if isinstance(budget, dict):
        cfg = UniverseCapabilities.from_dict({"graph_rag": budget}).graph_rag
    elif isinstance(budget, LlmBudget):
        cfg = budget
    else:
        return None
    if not cfg.enabled or not cfg.model.strip():
        return None
    return OpenAiCompatLlmAdapter(cfg)


def can_call_llm(adapter: LlmPort) -> bool:
    """Return True when the adapter still has remaining call and token budget."""
    rem_calls = getattr(adapter, "remaining_calls", None)
    rem_tokens = getattr(adapter, "remaining_tokens", None)
    if callable(rem_calls) and rem_calls() <= 0:
        return False
    if callable(rem_tokens) and rem_tokens() <= 0:
        return False
    return True
