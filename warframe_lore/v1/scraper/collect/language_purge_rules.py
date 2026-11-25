"""Pure helpers for language and off-topic purge decisions."""

from __future__ import annotations

from contextlib import nullcontext
from typing import Any, cast
from urllib.parse import urlparse

from .crawl_filter import (
    is_generalist_domain,
    keep_crawl_url,
    matches_universe_topic,
)
from .language import (
    canonical_locale_url_key,
    detect_url_locale,
    is_url_language_allowed,
)


def _batch(workspace: Any) -> Any:
    return workspace.batch_save() if hasattr(workspace, "batch_save") else nullcontext()


def _universe_keywords(workspace: Any, universe_id: str) -> list[str]:
    uni = workspace.get(universe_id) if hasattr(workspace, "get") else None
    raw = (
        " ".join(str(uni.get(f, "")) for f in ("name", "slug", "id"))
        if isinstance(uni, dict) else universe_id
    )
    words = [
        w.strip().lower() for w in raw.replace("-", " ").split() if len(w.strip()) >= 3
    ]
    return list(dict.fromkeys(words)) or [universe_id.strip().lower()]


def _approved_hosts(
    workspace: Any, universe_id: str, langs: tuple[str, ...]
) -> set[str]:
    hosts: set[str] = set()
    for key in ("sources", "candidates"):
        for item in cast(list[dict[str, Any]], workspace.data.get(key, [])):
            if str(item.get("universeId")) != universe_id or str(
                item.get("discoveredBy")
            ) in {"manifest_review", "keywords"}:
                continue
            loc = str(item.get("location", "")).strip()
            h = (urlparse(loc).hostname or "").lower().removeprefix("www.")
            if h and not h.endswith("example.org") and is_url_language_allowed(
                loc, langs
            ):
                extra = (h, "warframe.com") if h.endswith(".warframe.com") else (h,)
                hosts.update(extra)
    return hosts


def _filter_items(
    items: list[dict[str, Any]], uid: str, langs: tuple[str, ...],
    hosts: set[str], keywords: list[str],
) -> tuple[list[dict[str, Any]], int]:
    other = [i for i in items if str(i.get("universeId")) != uid]
    target = sorted(
        (i for i in items if str(i.get("universeId")) == uid),
        key=lambda i: (
            0 if str(i.get("discoveredBy")) != "manifest_review" else 1,
            0 if detect_url_locale(str(i.get("location", ""))) in langs else 1,
        ),
    )
    kept, seen_canon = [], set()
    for item in target:
        loc = str(item.get("location", "")).strip()
        h = (urlparse(loc).hostname or "").lower().removeprefix("www.")
        if (
            not loc
            or loc == "documents/warframe.pdf"
            or h.endswith("example.org")
            or not is_url_language_allowed(loc, langs)
        ):
            continue
        if is_generalist_domain(loc) and not matches_universe_topic(
            loc, str(item.get("title", "")), keywords
        ):
            continue
        if str(item.get("discoveredBy")) == "manifest_review":
            wf_ok = "warframe.com" in hosts and h.endswith("warframe.com")
            bad_sub = h.startswith(("store.", "support.", "www-static.", "forums."))
            bad_exp = (
                h == "origin.warframe.com" and "/publicexport/export" in loc.lower()
            )
            if (
                bad_sub
                or bad_exp
                or (hosts and h and h not in hosts and not wf_ok)
                or not keep_crawl_url(loc, "", allowed_languages=langs)
            ):
                continue
        if (canon := canonical_locale_url_key(loc)) not in seen_canon:
            seen_canon.add(canon)
            kept.append(item)
    return other + kept, len(target) - len(kept)
