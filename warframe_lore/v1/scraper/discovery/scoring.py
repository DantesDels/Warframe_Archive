"""Hybrid scoring and homonym filtering for discovery candidates."""

from __future__ import annotations

from dataclasses import replace
from typing import Any
from urllib.parse import urlparse

from .models import Candidate

_GENERIC_HOST_TOKENS = {"example", "github", "fandom", "wikipedia"}


def score_candidate(
    candidate: Candidate, universe: dict[str, Any], keywords: list[str]
) -> Candidate:
    name = str(universe.get("name", "")).lower()
    text = f"{candidate.title} {candidate.location} {candidate.proof}".lower()
    host = urlparse(candidate.location).netloc.lower()
    relevance = _relevance(text, keywords)
    authority = _authority(host, candidate.discovered_by)
    freshness = float(candidate.score_breakdown.get("freshness", 0.5))
    language = float(candidate.score_breakdown.get("language", 0.5))
    confidence = float(candidate.score_breakdown.get("confidence", candidate.score))
    breakdown = {
        "relevance": round(relevance, 3),
        "authority": round(authority, 3),
        "freshness": round(freshness, 3),
        "language": round(language, 3),
        "confidence": round(confidence, 3),
    }
    score = _weighted(breakdown)
    reason = _proof(breakdown)
    meta = dict(candidate.metadata)
    meta["score_reason"] = reason
    if _is_probable_homonym(name, text, relevance):
        score = min(score, 0.2)
        meta["homonym_risk"] = True
        reason = reason + " ; risque d'homonymie détecté"
    return replace(
        candidate,
        score=round(min(0.99, max(0.0, score)), 3),
        proof=reason,
        score_breakdown=breakdown,
        metadata=meta,
    )


def _relevance(text: str, keywords: list[str]) -> float:
    hits = sum(1 for k in keywords if k.lower() in text)
    if not keywords:
        return 0.3
    return min(1.0, 0.25 + (hits / max(len(keywords), 1)) * 0.75)


def _authority(host: str, discovered_by: str) -> float:
    if discovered_by in {"wiki", "sitemap"}:
        return 0.7
    if any(token in host for token in _GENERIC_HOST_TOKENS):
        return 0.45
    return 0.6


def _weighted(b: dict[str, float]) -> float:
    return (
        b["relevance"] * 0.45
        + b["authority"] * 0.2
        + b["freshness"] * 0.15
        + b["language"] * 0.1
        + b["confidence"] * 0.1
    )


def _proof(b: dict[str, float]) -> str:
    return (
        f"Pertinence {int(b['relevance'] * 100)}%, "
        f"autorit? {int(b['authority'] * 100)}%, "
        f"fra?cheur {int(b['freshness'] * 100)}%, "
        f"langue {int(b['language'] * 100)}%, "
        f"confiance extraction {int(b['confidence'] * 100)}%"
    )


def _is_probable_homonym(name: str, text: str, relevance: float) -> bool:
    if not name or relevance >= 0.45:
        return False
    tokens = [t for t in name.split() if len(t) >= 4]
    return bool(tokens) and not any(t in text for t in tokens)
