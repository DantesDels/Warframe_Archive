"""Pipeline stage: exact and near-duplicate detection."""

from __future__ import annotations

import hashlib
import re

from .base import PipelineContext, PipelineItem


class NearDedupeStage:
    name = "near_dedupe"

    def run(
        self, items: list[PipelineItem], _ctx: PipelineContext
    ) -> list[PipelineItem]:
        seen_sim: list[int] = []
        seen_minhash: list[set[int]] = []
        seen_sha: set[str] = set()
        for item in items:
            if not item.accepted:
                continue
            content = item.page.content or ""
            sha = hashlib.sha256(content.encode("utf-8", errors="ignore")).hexdigest()
            if sha in seen_sha:
                item.accepted = False
                item.reason = "duplicate_content"
                continue
            sim = _simhash(content)
            mh = _minhash(content)
            if any(_hamming(sim, prev) <= 6 for prev in seen_sim):
                item.accepted = False
                item.reason = "near_duplicate"
                continue
            if any(_jaccard(mh, prev) >= 0.75 for prev in seen_minhash):
                item.accepted = False
                item.reason = "near_duplicate"
                continue
            seen_sha.add(sha)
            seen_sim.append(sim)
            seen_minhash.append(mh)
        return items


def _tokens(text: str) -> list[str]:
    return re.findall(r"[\w']{3,}", text.lower())


def _simhash(text: str, bits: int = 64) -> int:
    tokens = _tokens(text)
    if not tokens:
        return 0
    v = [0] * bits
    for token in tokens:
        h = _hash64(token)
        for i in range(bits):
            v[i] += 1 if h & (1 << i) else -1
    out = 0
    for i, val in enumerate(v):
        if val >= 0:
            out |= 1 << i
    return out


def _minhash(text: str, size: int = 8) -> set[int]:
    tokens = _tokens(text)
    if not tokens:
        return set()
    hashes = sorted(_hash64(t) for t in set(tokens))
    return set(hashes[:size])


def _jaccard(a: set[int], b: set[int]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _hash64(token: str) -> int:
    h = 1469598103934665603
    for b in token.encode("utf-8", errors="ignore"):
        h ^= b
        h = (h * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    return h


def _hamming(a: int, b: int) -> int:
    return (a ^ b).bit_count()
