"""Resilience mechanics: Tenacity retry policy, retry guard and logging.

The pipeline applies:
- a Tenacity retry policy on every network-bound extraction method
  (3 attempts, exponential backoff, only transient failures retried);
- an ``asyncio.Semaphore`` (3 by default) to cap concurrent requests and
  avoid Fandom rate-limiting;
- native ``logging`` tracing each URL at INFO (attempt) and ERROR (failure).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

import aiohttp
from tenacity import (
    after_log,
    before_sleep_log,
    retry,
    retry_if_exception,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
DEFAULT_CONCURRENCY = 3

_retryable_exceptions: list[type[BaseException]] = [
    aiohttp.ClientConnectionError,
    aiohttp.ServerConnectionError,
    aiohttp.ClientError,
    asyncio.TimeoutError,
]


def _retry_policy(retry_check: Any, *, attempts: int = MAX_ATTEMPTS) -> Any:
    """Build a shared Tenacity policy (3 attempts, exponential backoff)."""
    return retry(
        stop=stop_after_attempt(attempts),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_check,
        reraise=True,
        after=after_log(logger, logging.ERROR),
        before_sleep=before_sleep_log(logger, logging.INFO),
    )


def retry_network(*, attempts: int = MAX_ATTEMPTS) -> Any:
    """Tenacity decorator: retry transient aiohttp/timeout failures.

    ``asyncio.TimeoutError`` (alias of builtin ``TimeoutError`` since
    Python 3.11) is deduplicated to avoid a duplicate-class TypeError in
    ``retry_if_exception_type``.
    """
    exceptions = tuple(dict.fromkeys(_retryable_exceptions))
    return _retry_policy(
        retry_if_exception_type(exceptions), attempts=attempts
    )


def retry_when(
    predicate: Callable[[BaseException], bool], *, attempts: int = MAX_ATTEMPTS
) -> Any:
    """Tenacity decorator retrying any exception satisfying ``predicate``."""
    return _retry_policy(retry_if_exception(predicate), attempts=attempts)


class ConcurrencyGuard:
    """Bounded-concurrency wrapper (semaphore) around an async callable."""

    def __init__(self, limit: int = DEFAULT_CONCURRENCY) -> None:
        if limit < 1:
            raise ValueError("limit doit être >= 1")
        self._semaphore = asyncio.Semaphore(limit)

    async def run(self, coroutine_factory: Any) -> Any:
        """Execute ``await coroutine_factory()`` under the semaphore."""
        async with self._semaphore:
            return await coroutine_factory()
