"""Concise grouped error summary for collection runs."""

from __future__ import annotations

from collections import Counter


def classify_run_error(error: str) -> str:
    """Bucket a raw collection error string into a human-readable category."""
    low = str(error or "").lower()
    rate_tokens = ("403", "429", "forbidden", "too many requests", "rate limit")
    if any(tok in low for tok in rate_tokens):
        return "HTTP 403/429"
    if any(tok in low for tok in ("timeout", "timed out", "délai", "deadline")):
        return "Timeout"
    if "404" in low or "not found" in low or "introuvable" in low:
        return "HTTP 404"
    if any(tok in low for tok in ("500", "502", "503", "504", "http 5")):
        return "HTTP 5xx"
    if "duplicate" in low or "doublon" in low:
        return "Doublon"
    if any(tok in low for tok in ("vide", "empty", "boilerplate", "trop court")):
        return "Contenu vide"
    net_tokens = (
        "dns", "getaddrinfo", "name or service", "connexion", "connection", "ssl",
    )
    if any(tok in low for tok in net_tokens):
        return "Réseau/DNS"
    if "playwright" in low:
        return "Playwright"
    return "Autre"


def summarize_run_errors(errors: list[str]) -> str:
    """Return a concise French breakdown of run errors sorted by frequency."""
    if not errors:
        return ""
    counts: Counter[str] = Counter(
        classify_run_error(err) for err in errors if str(err).strip()
    )
    if not counts:
        return ""
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    parts = [f"{count}x {label}" for label, count in ordered]
    return f"Erreurs : {', '.join(parts)}"
