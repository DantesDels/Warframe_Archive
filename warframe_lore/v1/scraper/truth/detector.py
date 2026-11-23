"""Deterministic cross-source alignment & conflict detection engine."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime

from ..semantic.models import canonical_key, stable_id
from .models import Claim, ConflictRecord, TemporalEvent
from .temporal import apply_temporal_supersession, value_signature


def detect_conflicts_and_history(
    claims: list[Claim],
    universe_id: str,
) -> tuple[list[Claim], list[ConflictRecord], list[TemporalEvent]]:
    """Align claims by (subject, predicate) to flag temporal updates & conflicts."""
    groups: dict[str, list[Claim]] = defaultdict(list)
    for claim in claims:
        groups[claim.normalized_key].append(claim)

    conflicts: list[ConflictRecord] = []
    history: list[TemporalEvent] = []
    now = datetime.now(UTC).isoformat()

    for bucket in groups.values():
        active = apply_temporal_supersession(bucket, history)
        if len(active) >= 2:
            _detect_group_conflicts(active, universe_id, now, conflicts)
    return claims, conflicts, history


def _detect_group_conflicts(
    active: list[Claim],
    universe_id: str,
    now: str,
    conflicts: list[ConflictRecord],
) -> None:
    by_sig: dict[str, list[Claim]] = defaultdict(list)
    for claim in active:
        by_sig[value_signature(claim)].append(claim)
    if len(by_sig) < 2:
        return

    reps = [
        max(group, key=lambda c: (c.trust_weight, c.timestamp))
        for group in by_sig.values()
    ]
    ranked = sorted(reps, key=lambda c: (-c.trust_weight, c.id))
    lead = ranked[0]
    for challenger in ranked[1:]:
        if _values_compatible(lead, challenger):
            continue
        lead.status = "conflicting"
        challenger.status = "conflicting"
        pair_ids = sorted([lead.id, challenger.id])
        cid = stable_id("cnf", universe_id, lead.normalized_key, *pair_ids)
        conflicts.append(
            ConflictRecord(
                id=cid, universe_id=universe_id, subject=lead.subject,
                predicate=lead.predicate, claim_a_id=lead.id,
                claim_b_id=challenger.id, value_a=lead.value,
                value_b=challenger.value,
                source_a_profile=lead.trust_profile,
                source_b_profile=challenger.trust_profile,
                evidence_a=lead.evidence, evidence_b=challenger.evidence,
                url_a=lead.url, url_b=challenger.url,
                reason=_conflict_reason(lead, challenger),
                recommended=_recommend(lead, challenger),
                status="open", created_at=now,
            )
        )


def _values_compatible(a: Claim, b: Claim) -> bool:
    if a.polarity != b.polarity:
        return False
    ka, kb = canonical_key(a.value), canonical_key(b.value)
    return ka == kb or (len(ka) > 4 and len(kb) > 4 and (ka in kb or kb in ka))


def _conflict_reason(a: Claim, b: Claim) -> str:
    if a.polarity != b.polarity:
        return "Polarité contradictoire (affirmation vs négation)"
    return f"Valeurs divergentes ({a.value} vs {b.value})"


def _recommend(a: Claim, b: Claim) -> str:
    if a.trust_weight > b.trust_weight + 0.05:
        return "keep_a"
    if b.trust_weight > a.trust_weight + 0.05:
        return "keep_b"
    if a.timestamp and b.timestamp and a.timestamp != b.timestamp:
        return "keep_a" if a.timestamp > b.timestamp else "keep_b"
    return "none"
