"""Bounded network primitives shared by outbound adapters."""

from __future__ import annotations

import socket
from concurrent.futures import ThreadPoolExecutor
from typing import Any, cast

CONNECT_TIMEOUT = 5.0
READ_TIMEOUT = 15.0
HTTP_TIMEOUT = (CONNECT_TIMEOUT, READ_TIMEOUT)
DNS_TIMEOUT = 2.0

_RESOLVER = ThreadPoolExecutor(max_workers=2, thread_name_prefix="v1-dns")


def resolve_host(host: str, timeout: float = DNS_TIMEOUT) -> list[Any]:
    """Resolve a host without blocking the caller beyond ``timeout`` seconds."""
    if not host:
        return []
    try:
        future = _RESOLVER.submit(socket.getaddrinfo, host, None)
        return cast(list[Any], future.result(timeout=timeout))
    except Exception:
        return []
