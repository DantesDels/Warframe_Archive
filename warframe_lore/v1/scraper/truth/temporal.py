"""Temporal supersession tracking for same-source evolving claims."""

from __future__ import annotations

from collections import defaultdict

from ..semantic.models import canonical_key
from .models import Claim, TemporalEvent


def value_signature(claim: Claim) -> str:
    """Return canonical polarity+value signature for claim comparison."""
    return f"{claim.polarity}:{canonical_key(claim.value)}"


def apply_temporal_supersession(
    bucket: list[Claim], history: list[TemporalEvent]
) -> list[Claim]:
    """Mark older same-source claims obsolete when superseded by newer ones."""
    by_source: dict[str, list[Claim]] = defaultdict(list)
    for claim in bucket:
        origin = claim.source_id or claim.document_id
        by_source[origin].append(claim)

    active: list[Claim] = []
    for origin, items in by_source.items():
        if len(items) == 1:
            active.append(items[0])
            continue
        ordered = sorted(items, key=lambda c: (c.timestamp, c.document_id, c.chunk_id))
        latest = ordered[-1]
        latest_sig = value_signature(latest)
        for older in ordered[:-1]:
            if value_signature(older) == latest_sig:
                continue
            older.status = "obsolete"
            older.valid_to = latest.timestamp or latest.valid_from
            older.superseded_by = latest.id
            history.append(
                TemporalEvent(
                    subject=latest.subject,
                    predicate=latest.predicate,
                    old_claim_id=older.id,
                    new_claim_id=latest.id,
                    old_value=older.value,
                    new_value=latest.value,
                    changed_at=latest.timestamp or latest.valid_from,
                    source_id=origin,
                    reason="Mise à jour temporelle sur la même source",
                )
            )
        active.append(latest)
    return active
