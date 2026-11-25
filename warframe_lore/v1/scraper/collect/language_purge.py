"""Pure-Python language and off-topic generalist-domain purge for workspaces."""

from __future__ import annotations

from typing import Any, cast

from .language import (
    DEFAULT_ALLOWED_LANGUAGES,
    normalize_allowed_languages,
)
from .language_purge_rules import (
    _approved_hosts,
    _batch,
    _filter_items,
    _universe_keywords,
)


def universe_allowed_languages(workspace: Any, universe_id: str) -> tuple[str, ...]:
    """Return configured allowed language codes for one universe (default EN)."""
    has_caps = hasattr(workspace, "capabilities_for") and universe_id
    caps = workspace.capabilities_for(universe_id) if has_caps else {}
    raw = caps.get("allowed_languages") if isinstance(caps, dict) else None
    return normalize_allowed_languages(raw) if raw else DEFAULT_ALLOWED_LANGUAGES


def set_universe_allowed_languages(
    ws: Any, uid: str, languages: Any
) -> tuple[str, ...]:
    """Persist allowed language codes on the universe capabilities."""
    norm = normalize_allowed_languages(languages)
    if hasattr(ws, "capabilities_for") and hasattr(ws, "set_capabilities"):
        old = ws.capabilities_for(uid)
        ws.set_capabilities(uid, {**old, "allowed_languages": list(norm)})
    return norm


def scan_disallowed_and_off_topic(
    workspace: Any, universe_id: str, allowed_languages: Any = None
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int, int]:
    """Scan workspace and return (kept_sources, kept_candidates, rem_s, rem_c)."""
    langs = normalize_allowed_languages(
        allowed_languages or universe_allowed_languages(workspace, universe_id)
    )
    kw = _universe_keywords(workspace, universe_id)
    hosts = _approved_hosts(workspace, universe_id, langs)
    srcs = cast(list[dict[str, Any]], workspace.data.get("sources", []))
    cands = cast(list[dict[str, Any]], workspace.data.get("candidates", []))
    kept_s, rem_s = _filter_items(srcs, universe_id, langs, hosts, kw)
    kept_c, rem_c = _filter_items(cands, universe_id, langs, hosts, kw)
    return kept_s, kept_c, rem_s, rem_c


def purge_disallowed_languages_and_duplicates(
    workspace: Any, universe_id: str, allowed_languages: Any = None
) -> tuple[int, int]:
    """Remove non-selected language URLs, off-topic generalist pages and duplicates."""
    ks, kc, rs, rc = scan_disallowed_and_off_topic(
        workspace, universe_id, allowed_languages
    )
    if rs or rc:
        with _batch(workspace):
            workspace.data["sources"], workspace.data["candidates"] = ks, kc
            if hasattr(workspace, "save"):
                workspace.save()
    return rs, rc
