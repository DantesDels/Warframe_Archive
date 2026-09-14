"""Small reusable HTTP layer: retries + backoff + throttling.

Also handles API errors that come back as HTTP 200 (the ``error`` field
of the JSON).  Encapsulated separately so it can be reused by other
potential clients (DRY principle).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from typing import Any

import requests

log = logging.getLogger("warframe_lore.api.mediawiki")


class MediaWikiSourceError(RuntimeError):
    """Non-transient MediaWiki API error."""


class RetryableHttp:
    """GET + exponential retries + politeness throttle between requests."""

    def __init__(self, api_url: str, user_agent: str, *, timeout: float = 60.0,
                 max_retries: int = 5, retry_backoff: float = 2.0,
                 min_sleep: float = 0.4, per_request_limit: int = 50) -> None:
        self.api_url = api_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self.min_sleep = min_sleep
        self.per_request_limit = per_request_limit
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})
        self._last_request_ts = 0.0

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_ts
        wait = self.min_sleep - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_request_ts = time.monotonic()

    def request(self, params: dict[str, Any]) -> dict[str, Any]:
        """GET + retries + backoff, returns the parsed JSON."""
        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            self._throttle()
            try:
                resp = self.session.get(self.api_url, params=params,
                                        timeout=self.timeout)
                resp.raise_for_status()
                data = resp.json()
            except (requests.RequestException, ValueError) as exc:
                last_exc = exc
                backoff = self.retry_backoff ** attempt
                log.warning("Request failed (%d/%d): %s; retrying in %.1fs",
                            attempt + 1, self.max_retries, exc, backoff)
                time.sleep(backoff)
                continue

            if "error" in data:
                code = data["error"].get("code", "unknown")
                if code in {"ratelimited", "maxlag"}:
                    time.sleep(self.retry_backoff)
                    continue
                raise MediaWikiSourceError(
                    f"API error '{code}': {data['error'].get('info', '')}")
            return data

        raise MediaWikiSourceError(
            f"Request failed after {self.max_retries} attempts: {last_exc}")

    def paged(self, params: dict[str, Any]) -> Iterator[dict[str, Any]]:
        """Iterates over result pages following the ``continue`` token."""
        p = dict(params)
        while True:
            data = self.request(p)
            yield data
            cont = data.get("continue", {})
            if not cont:
                break
            p.update({k: v for k, v in cont.items() if k != "continue"})
