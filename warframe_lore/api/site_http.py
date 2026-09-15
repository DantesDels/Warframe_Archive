"""Lightweight HTML-site HTTP transport: retries + backoff + throttle.

``www.warframe.com`` is a plain HTML site (no JSON MediaWiki API), so the
MediaWiki-specific :class:`RetryableHttp` cannot be reused.  This class keeps
the same politeness discipline (``min_sleep`` between requests, exponential
backoff on transient failures) while fetching raw pages and their freshness
signal (``ETag`` / ``Last-Modified`` from the ``HEAD`` response).
"""

from __future__ import annotations

import time

import requests


class SiteHttp:
    """GET/HEAD on a single host with retries, backoff and throttling."""

    def __init__(self, site_url: str, user_agent: str, *, timeout: float = 60.0,
                 max_retries: int = 5, retry_backoff: float = 2.0,
                 min_sleep: float = 0.4) -> None:
        self.site_url = site_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self.min_sleep = min_sleep
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})
        self._last_request_ts = 0.0

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_ts
        wait = self.min_sleep - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_request_ts = time.monotonic()

    def _request(self, method: str, path: str, headers=None):
        url = self.site_url + (path if path.startswith("/") else "/" + path)
        for attempt in range(self.max_retries):
            self._throttle()
            try:
                resp = self.session.request(method, url, timeout=self.timeout,
                                            headers=headers)
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                return resp
            except requests.RequestException:
                if attempt + 1 >= self.max_retries:
                    raise
                time.sleep(self.retry_backoff ** attempt)

    def get_text(self, path: str) -> str | None:
        """GET the page and return its raw HTML (None when it 404s)."""
        resp = self._request("GET", path)
        return None if resp is None else resp.text

    def fetch(self, path: str) -> tuple[str, str | None] | None:
        """GET the page: raw HTML + its freshness signal (ETag/Last-Modified)."""
        resp = self._request("GET", path)
        if resp is None:
            return None
        touched = resp.headers.get("ETag") or resp.headers.get("Last-Modified")
        return resp.text, touched

    def head(self, path: str):
        """HEAD the page; ``None`` when it is missing (404)."""
        return self._request("HEAD", path)


__all__ = ["SiteHttp"]
