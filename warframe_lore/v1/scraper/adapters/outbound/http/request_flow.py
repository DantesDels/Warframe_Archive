"""Retry-aware HTTP request execution for the outbound adapter."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import requests

from ....observability.progress import ProgressReporter
from .models import FetchResponse


def request_with_retries(
    *,
    session: Any,
    url: str,
    headers: dict[str, str],
    params: dict[str, Any] | None,
    allow_redirects: bool,
    timeout: float | tuple[float, float],
    verify: str,
    max_retries: int,
    backoff: float,
    reporter: ProgressReporter,
    control: Any,
    throttle: Callable[[], None],
) -> FetchResponse:
    """Execute one GET with bounded retries and live feedback."""
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        if control is not None and control.is_cancelled():
            raise InterruptedError("Exécution annulée par l'utilisateur.")
        throttle()
        try:
            response = session.get(
                url,
                params=params,
                headers=headers,
                timeout=timeout,
                verify=verify,
                allow_redirects=allow_redirects,
            )
            if response.status_code in {408, 429, 500, 502, 503, 504}:
                last_exc = requests.HTTPError(response=response)
                raw_retry_after = str(
                    response.headers.get("Retry-After", "")
                ).strip()
                long_429 = (
                    response.status_code == 429
                    and raw_retry_after.isdigit()
                    and int(raw_retry_after) > 10
                )
                if attempt + 1 >= max_retries or long_429:
                    suf = f" retry-after={raw_retry_after}" if raw_retry_after else ""
                    raise RuntimeError(f"HTTP {response.status_code} {url}{suf}")
                wait = _retry_after(raw_retry_after, backoff, attempt)
                reporter.retry(attempt + 2, max_retries, wait,
                               f"HTTP {response.status_code}")
                _sleep(wait)
                continue
            if response.status_code not in {200, 304}:
                response.raise_for_status()
            body = response.content if response.status_code != 304 else b""
            return FetchResponse(
                str(response.url),
                int(response.status_code),
                body,
                str(response.headers.get("Content-Type", "")),
                {str(key): str(value) for key, value in response.headers.items()},
                response.encoding,
            )
        except requests.HTTPError:
            raise
        except requests.RequestException as exc:
            last_exc = exc
            if attempt + 1 >= max_retries:
                raise
            wait = min(float(backoff**attempt), 5.0)
            reporter.retry(attempt + 2, max_retries, wait, str(exc))
            _sleep(wait)
    raise RuntimeError(f"GET failed: {last_exc}")


def _retry_after(raw: str, backoff: float, attempt: int) -> float:
    delay = int(raw) if raw.isdigit() else backoff**attempt
    return min(float(delay), 5.0)


def _sleep(seconds: float) -> None:
    time.sleep(max(0.0, seconds))
