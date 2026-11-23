"""Conditional HTTP probing (ETag / Last-Modified / 304) for watch targets."""

from __future__ import annotations

from typing import Any

import requests

from ..adapters.outbound.http.headers import bot_headers
from ..security.fetch_policy import check_url
from .detectors import extract_change_fingerprint
from .models import WatchCheckResult, WatchTarget, utc_now_iso


def probe_target(
    target: WatchTarget,
    *,
    client: Any | None = None,
    timeout: tuple[float, float] = (5.0, 15.0),
) -> WatchCheckResult:
    """Issue a conditional GET and report whether the watched source changed."""
    checked_at = utc_now_iso()
    scan = check_url(target.url)
    if not scan.allowed:
        return WatchCheckResult(
            target=target, changed=False, status_code=0,
            reason=f"URL bloquée : {scan.reason}", checked_at=checked_at,
            error=scan.reason,
        )
    headers = dict(bot_headers())
    if target.etag:
        headers["If-None-Match"] = target.etag
    if target.last_modified:
        headers["If-Modified-Since"] = target.last_modified
    try:
        resp = _do_get(target.url, headers=headers, timeout=timeout, client=client)
    except Exception as exc:  # noqa: BLE001
        return WatchCheckResult(
            target=target, changed=False, status_code=0,
            reason=f"Erreur réseau : {exc}", checked_at=checked_at, error=str(exc),
        )
    status = int(getattr(resp, "status_code", 0))
    raw_hdrs = getattr(resp, "headers", None) or {}
    resp_headers = {str(k).lower(): str(v) for k, v in raw_hdrs.items()}
    new_etag = resp_headers.get("etag", target.etag)
    new_lm = resp_headers.get("last-modified", target.last_modified)
    if status == 304:
        return WatchCheckResult(
            target=target, changed=False, status_code=304, not_modified=True,
            reason="304 Not Modified (aucun changement)",
            new_etag=new_etag, new_last_modified=new_lm,
            new_fingerprint=target.fingerprint, checked_at=checked_at,
        )
    if status >= 400 or status == 0:
        return WatchCheckResult(
            target=target, changed=False, status_code=status,
            reason=f"HTTP {status}", checked_at=checked_at, error=f"HTTP {status}",
        )
    body = bytes(getattr(resp, "content", b"") or b"")
    fingerprint, items = extract_change_fingerprint(target.watcher_kind, body)
    is_baseline = not (target.fingerprint or target.etag or target.last_modified)
    if is_baseline:
        return WatchCheckResult(
            target=target, changed=False, status_code=status,
            reason="Référence initiale enregistrée",
            detected_items=items, new_etag=new_etag, new_last_modified=new_lm,
            new_fingerprint=fingerprint, checked_at=checked_at,
        )
    headers_changed = new_etag != target.etag or new_lm != target.last_modified
    changed = (
        (bool(target.fingerprint) and fingerprint != target.fingerprint)
        or (not target.fingerprint and headers_changed)
    )
    msg = (
        f"Changement détecté ({len(items)} élément(s))"
        if changed
        else "Contenu identique (empreinte inchangée)"
    )
    return WatchCheckResult(
        target=target, changed=changed, status_code=status,
        reason=msg, detected_items=items, new_etag=new_etag,
        new_last_modified=new_lm, new_fingerprint=fingerprint, checked_at=checked_at,
    )


def _do_get(
    url: str,
    *,
    headers: dict[str, str],
    timeout: tuple[float, float],
    client: Any | None,
) -> Any:
    if client is not None:
        return client.get(url, headers=headers, timeout=timeout)
    return requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
