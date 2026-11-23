"""Outbound HTTP adapter: retries, cache, robots, security policy."""

from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

import certifi
import requests

from ....adapters.outbound.persistence.quarantine import QuarantineStore
from ....collect.cache import FetchCache
from ....observability.network import HTTP_TIMEOUT
from ....observability.progress import ProgressReporter, stop_requested
from ....ports.outbound.events import EventLogPort
from ....security.fetch_policy import FetchPolicy
from .cache_flow import cache_key, conditional_headers, from_cached, store
from .headers import browser_headers
from .models import FetchResponse
from .request_flow import request_with_retries
from .robots import RobotsPolicy
from .security_flow import RequestGuard


class HttpClientAdapter:
    """Outbound HTTP adapter. Enforces URL/payload policy and robots."""

    def __init__(
        self,
        *,
        timeout: float | tuple[float, float] = HTTP_TIMEOUT,
        max_retries: int = 4,
        backoff: float = 1.5,
        min_sleep: float = 0.2,
        cache: FetchCache | None = None,
        policy: FetchPolicy | None = None,
        robots: RobotsPolicy | None = None,
        event_log: EventLogPort | None = None,
        quarantine: QuarantineStore | None = None,
        reporter: ProgressReporter | None = None,
        control: Any | None = None,
    ) -> None:
        self.timeout = timeout
        self.reporter = reporter or ProgressReporter()
        self.control = control
        self.max_retries = max_retries
        self.backoff = backoff
        self.min_sleep = min_sleep
        self.cache = cache
        self.robots = robots or RobotsPolicy()
        self.event_log = event_log
        self._last = 0.0
        self.session = requests.Session()
        self.verify = certifi.where()
        self.guard = RequestGuard(
            policy=policy or FetchPolicy(),
            robots=self.robots,
            event_log=event_log,
            quarantine=quarantine,
            reporter=self.reporter,
        )

    def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str | int | float | bool | None] | None = None,
        allow_redirects: bool = True,
        use_cache: bool = True,
    ) -> FetchResponse:
        if self.control is not None and stop_requested({}, self.control):
            raise InterruptedError("Exécution annulée par l'utilisateur.")
        req_headers = dict(headers or browser_headers())
        self.guard.check_url(url, req_headers)
        key = cache_key(url, dict(params) if params else None, req_headers)
        cached = self.cache.get(key) if self.cache and use_cache else None
        headers_for_request = conditional_headers(req_headers, cached)
        params_dict = dict(params) if params else None
        response = self._request(
            url, headers_for_request, params_dict, allow_redirects
        )
        if response.status == 304 and cached and self.cache:
            response = from_cached(self.cache, key, cached, url)
        self.guard.check_payload(response)
        if use_cache:
            store(self.cache, key, response)
        self.reporter.http(response.url, response.status,
                           from_cache=response.from_cache)
        if self.event_log is not None:
            self.event_log.emit(
                "fetch_ok", url=response.url, status=response.status,
                cache=response.from_cache,
            )
        return response

    def _request(
        self,
        url: str,
        headers: dict[str, str],
        params: dict[str, Any] | None,
        allow_redirects: bool,
    ) -> FetchResponse:
        return request_with_retries(
            session=self.session,
            url=url,
            headers=headers,
            params=params,
            allow_redirects=allow_redirects,
            timeout=self.timeout,
            verify=self.verify,
            max_retries=self.max_retries,
            backoff=self.backoff,
            reporter=self.reporter,
            control=self.control,
            throttle=lambda: self._throttle(url, headers.get("User-Agent", "*")),
        )

    def _throttle(self, url: str, user_agent: str) -> None:
        delay = max(self.min_sleep, self.robots.crawl_delay(url, user_agent))
        wait = delay - (time.monotonic() - self._last)
        if wait > 0 and not (self.control and self.control.is_cancelled()):
            time.sleep(wait)
        self._last = time.monotonic()
