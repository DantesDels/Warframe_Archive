"""Outbound HTTP adapter: retries, cache, robots, security policy."""

from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

import certifi
import requests

from ....adapters.outbound.persistence.quarantine import QuarantineStore
from ....collect.cache import FetchCache
from ....ports.outbound.events import EventLogPort
from ....security.fetch_policy import FetchPolicy, check_payload, check_url
from ....security.models import ScanResult
from .cache_flow import cache_key, conditional_headers, store
from .headers import browser_headers
from .robots import RobotsPolicy


@dataclass(slots=True)
class FetchResponse:
    url: str
    status: int
    content: bytes
    content_type: str
    headers: dict[str, str]
    encoding: str | None
    from_cache: bool = False


class HttpClientAdapter:
    """Outbound HTTP adapter. Enforces URL/payload policy and robots."""

    def __init__(
        self,
        *,
        timeout: float = 25.0,
        max_retries: int = 4,
        backoff: float = 1.5,
        min_sleep: float = 0.2,
        cache: FetchCache | None = None,
        policy: FetchPolicy | None = None,
        robots: RobotsPolicy | None = None,
        event_log: EventLogPort | None = None,
        quarantine: QuarantineStore | None = None,
    ) -> None:
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff = backoff
        self.min_sleep = min_sleep
        self.cache = cache
        self.policy = policy or FetchPolicy()
        self.robots = robots or RobotsPolicy()
        self.event_log = event_log
        self.quarantine = quarantine
        self._last = 0.0
        self.session = requests.Session()
        self.verify = certifi.where()

    def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str | int | float | bool | None] | None = None,
        allow_redirects: bool = True,
        use_cache: bool = True,
    ) -> FetchResponse:
        req_headers = dict(headers or browser_headers())
        self._check_url(url, req_headers)
        key = cache_key(url, dict(params) if params else None, req_headers)
        cached = self.cache.get(key) if self.cache and use_cache else None
        cond = conditional_headers(req_headers, cached)
        resp = self._request(url, cond, dict(params) if params else None,
            allow_redirects)
        if resp.status == 304 and cached and self.cache:
            content = self.cache.get_content(key) or b""
            resp = FetchResponse(
                str(cached.get("url", url)),
                200,
                content,
                str(cached.get("content_type", "")),
                cast(dict[str, str], cached.get("headers", {})),
                cast(str | None, cached.get("encoding")),
                from_cache=True,
            )
        self._check_payload(resp)
        if use_cache:
            store(self.cache, key, resp)
        self._emit("fetch_ok", url=resp.url, status=resp.status, cache=resp.from_cache)
        return resp

    def _check_url(self, url: str, headers: dict[str, str]) -> None:
        verdict = check_url(url, self.policy)
        if not verdict.allowed:
            self._reject(url, verdict)
        ua = str(headers.get("User-Agent", "*"))
        if not self.robots.allowed(url, ua):
            verdict = ScanResult(False, "Bloqu? par robots.txt.", "blocked_robots", url)
            self._reject(url, verdict)

    def _check_payload(self, resp: FetchResponse) -> None:
        verdict = check_payload(resp.url, resp.content, resp.content_type, self.policy)
        if not verdict.allowed:
            if self.quarantine:
                self.quarantine.put(resp.url, resp.content, verdict.reason,
                    verdict.code)
            self._reject(resp.url, verdict)

    def _reject(self, url: str, verdict: ScanResult) -> None:
        self._emit("security_blocked", url=url, code=verdict.code,
            reason=verdict.reason)
        raise PermissionError(f"{verdict.code}: {verdict.reason}")

    def _emit(self, event_type: str, **payload: Any) -> None:
        if self.event_log:
            self.event_log.emit(event_type, **payload)

    def _request(
        self,
        url: str,
        headers: dict[str, str],
        params: dict[str, Any] | None,
        allow_redirects: bool,
    ) -> FetchResponse:
        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            self._throttle(url, headers.get("User-Agent", "*"))
            try:
                r = self.session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=self.timeout,
                    verify=self.verify,
                    allow_redirects=allow_redirects,
                )
                if r.status_code in {429, 500, 502, 503, 504}:
                    last_exc = requests.HTTPError(response=r)
                    time.sleep(self.backoff**attempt)
                    continue
                if r.status_code not in {200, 304}:
                    r.raise_for_status()
                body = r.content if r.status_code != 304 else b""
                return FetchResponse(
                    str(r.url),
                    int(r.status_code),
                    body,
                    str(r.headers.get("Content-Type", "")),
                    {str(k): str(v) for k, v in r.headers.items()},
                    cast(str | None, r.encoding),
                )
            except requests.RequestException as exc:
                last_exc = exc
                if attempt + 1 >= self.max_retries:
                    raise
                time.sleep(self.backoff**attempt)
        raise RuntimeError(f"GET failed: {last_exc}")

    def _throttle(self, url: str, ua: str) -> None:
        delay = max(self.min_sleep, self.robots.crawl_delay(url, ua))
        wait = delay - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()
