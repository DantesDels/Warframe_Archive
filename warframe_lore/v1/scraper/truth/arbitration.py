"""Human arbitration state updates for inter-source conflicts & claim status."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def truth_state_for(workspace: Any, universe_id: str) -> dict[str, Any]:
    """Return the persisted truth snapshot dict for one universe."""
    store = workspace.data.get("truth_state")
    entry = store.get(universe_id) if isinstance(store, dict) else None
    if isinstance(entry, dict):
        return entry
    return {"claims": [], "conflicts": [], "history": [], "stats": {}}


def conflicts_for(workspace: Any, universe_id: str) -> list[dict[str, Any]]:
    """Return all conflict records stored for one universe."""
    items = truth_state_for(workspace, universe_id).get("conflicts")
    return list(items) if isinstance(items, list) else []


def open_conflicts_count(workspace: Any, universe_id: str) -> int:
    """Count open conflicts awaiting human arbitration for one universe."""
    return sum(
        1 for c in conflicts_for(workspace, universe_id) if c.get("status") == "open"
    )


def resolve_conflict(
    workspace: Any, universe_id: str, conflict_id: str, decision: str, *, note: str = ""
) -> dict[str, Any] | None:
    """Apply a human arbitration decision and update linked claim statuses."""
    if decision not in {"keep_a", "keep_b", "obsolete", "dismiss"}:
        raise ValueError(f"Unsupported arbitration decision: {decision}")
    state = truth_state_for(workspace, universe_id)
    conflicts = state.get("conflicts")
    if not isinstance(conflicts, list):
        return None
    target = next((c for c in conflicts if c.get("id") == conflict_id), None)
    if target is None:
        return None

    now = datetime.now(UTC).isoformat()
    by_id = {
        str(c.get("id")): c for c in (state.get("claims") or []) if isinstance(c, dict)
    }
    claim_a = by_id.get(str(target.get("claim_a_id", "")))
    claim_b = by_id.get(str(target.get("claim_b_id", "")))
    _apply_decision(decision, target, claim_a, claim_b, state, now, note)
    if hasattr(workspace, "save"):
        workspace.save()
    return target


def _apply_decision(
    decision: str, conflict: dict[str, Any], claim_a: dict[str, Any] | None,
    claim_b: dict[str, Any] | None, state: dict[str, Any], now: str, note: str,
) -> None:
    conflict["resolved_at"] = now
    conflict["resolution_note"] = note.strip()
    history = state.setdefault("history", [])
    if decision in {"keep_a", "keep_b"}:
        kept, dropped = ("a", "b") if decision == "keep_a" else ("b", "a")
        winner, loser = (claim_a, claim_b) if kept == "a" else (claim_b, claim_a)
        win_id = str(conflict.get(f"claim_{kept}_id", ""))
        conflict["status"] = f"resolved_{kept}"
        conflict["winning_claim_id"] = win_id
        _mark(winner, "confirmed")
        _supersede(loser, win_id, now)
        history.append({
            "subject": conflict.get("subject", ""),
            "predicate": conflict.get("predicate", ""),
            "old_claim_id": conflict.get(f"claim_{dropped}_id", ""),
            "new_claim_id": win_id,
            "old_value": conflict.get(f"value_{dropped}", ""),
            "new_value": conflict.get(f"value_{kept}", ""),
            "changed_at": now, "source_id": "human_arbitration",
            "reason": "Arbitrage humain",
        })
    elif decision == "obsolete":
        conflict["status"], conflict["winning_claim_id"] = "obsolete", ""
        _supersede(claim_a, "", now)
        _supersede(claim_b, "", now)
    else:
        conflict["status"], conflict["winning_claim_id"] = "dismissed", ""
        _mark(claim_a, "confirmed")
        _mark(claim_b, "confirmed")


def _mark(claim: dict[str, Any] | None, status: str) -> None:
    if claim is not None:
        claim["status"] = status


def _supersede(claim: dict[str, Any] | None, winner_id: str, when: str) -> None:
    if claim is not None:
        claim["status"], claim["valid_to"] = "obsolete", when
        if winner_id:
            claim["superseded_by"] = winner_id
