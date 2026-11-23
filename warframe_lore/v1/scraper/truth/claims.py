"""Deterministic FR/EN extraction of atomic claims with chunk provenance."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..semantic.models import canonical_key, stable_id
from ..semantic.patterns import STOP_ENTITIES
from ..semantic.runtime_helpers import hydrate_doc
from ..UI.runtime.rag_chunks import iter_doc_chunks
from .claim_patterns import CLAIM_PATTERNS, NEGATION_RE, SENTENCE_RE
from .models import Claim
from .trust import trust_weight

_MAX_CLAIMS_PER_DOC = 60
_IGNORED_KV_KEYS = frozenset({
    "main article", "article principal", "see also", "voir aussi",
    "note", "notes", "warning", "attention", "tip", "astuce", "example",
})


def extract_doc_claims(
    doc: dict[str, Any],
    *,
    trust_profile: str = "third_party",
    blob_root: Path | None = None,
) -> list[Claim]:
    """Extract normalized atomic claims from one document with chunk provenance."""
    hydrated = hydrate_doc(doc, blob_root)
    doc_id = str(hydrated.get("id") or "doc")
    source_id = str(hydrated.get("sourceId") or "")
    url = str(hydrated.get("url") or "")
    timestamp = _doc_timestamp(hydrated)
    weight = trust_weight(trust_profile)
    claims: list[Claim] = []
    seen: set[tuple[str, str, str]] = set()

    for idx, (chunk, _section) in enumerate(iter_doc_chunks(hydrated)):
        chunk_id = f"{doc_id}::{idx}"
        for raw_sent in SENTENCE_RE.split(chunk):
            sent = " ".join(raw_sent.split()).strip()
            if len(sent) < 10:
                continue
            for predicate, pattern in CLAIM_PATTERNS:
                for match in pattern.finditer(sent):
                    subj = _clean_span(match.group(1))
                    val = _clean_span(match.group(2))
                    skey, vkey = canonical_key(subj), canonical_key(val)
                    if _invalid_claim(skey, vkey):
                        continue
                    polarity = "negate" if NEGATION_RE.search(sent) else "affirm"
                    sig = (skey, predicate, f"{polarity}:{vkey}")
                    if sig in seen:
                        continue
                    seen.add(sig)
                    cid = stable_id("clm", source_id or doc_id, chunk_id, *sig)
                    claims.append(
                        Claim(
                            id=cid, subject=subj, predicate=predicate, value=val,
                            normalized_key=f"{skey}|{predicate}",
                            polarity=polarity, source_id=source_id,
                            document_id=doc_id, chunk_id=chunk_id, url=url,
                            trust_profile=trust_profile, trust_weight=weight,
                            timestamp=timestamp, valid_from=timestamp,
                            evidence=sent[:220],
                        )
                    )
                    if len(claims) >= _MAX_CLAIMS_PER_DOC:
                        return claims
    return claims


def _clean_span(raw: str) -> str:
    return " ".join(raw.split()).strip(" -:,;()[]\"'.")


def _invalid_claim(skey: str, vkey: str) -> bool:
    if not skey or not vkey or skey == vkey or len(skey) < 3:
        return True
    if skey in _IGNORED_KV_KEYS:
        return True
    return skey in STOP_ENTITIES or vkey in STOP_ENTITIES


def _doc_timestamp(doc: dict[str, Any]) -> str:
    for key in ("updatedAt", "fetchedAt", "publishedAt", "timestamp", "lastSeenRunId"):
        val = str(doc.get(key) or "").strip()
        if val:
            return val
    return ""
