"""French log lines for pipeline events surfaced in the execution panel."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def format_event(event_type: str, payload: Any) -> str:
    data = payload if isinstance(payload, Mapping) else {}
    if event_type == "universe_started":
        return f"Univers démarré : {data.get('sources', 0)} source(s) active(s)."
    if event_type == "universe_finished":
        count = data.get("docs", 0)
        errors = data.get("errors", 0)
        return f"Univers terminé : {count} document(s), {errors} erreur(s)."
    if event_type == "source_warning":
        return f"Avertissement source : {data.get('message', '')}"
    if event_type == "children_pending_review":
        return f"{data.get('count', 0)} page(s) enfant(s) en attente de revue."
    return ""
