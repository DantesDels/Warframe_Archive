"""Retrying HTTP client for v1 collection."""

from __future__ import annotations

import time
from dataclasses import dataclass

import certifi
import requests

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 AtelierV1/1.0"
)
BOT_UA = "AtelierV1/1.0 (+local data collection; contact: local)"


@dataclass(slots=True)
class FetchResponse:
    url: str
    status: int
    content: bytes
    content_type: str
    headers: dict[str, str]
    encoding: str | None


class HttpClient:
    def __init__(self, *, timeout: float = 25.0, max_retries: int = 4,
                 backoff: float = 1.5, min_sleep: float = 0.2) -> None:
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff = backoff
        self.min_sleep = min_sleep
        self._last = 0.0
        self.session = requests.Session()
        self.verify = certifi.where()

    def get(self, url: str, *, headers: dict[str, str] | None = None,
            params: dict | None = None, allow_redirects: bool = True) -> FetchResponse:
        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            self._throttle()
            try:
                resp = self.session.get(
                    url, params=params, headers=headers or browser_headers(),
                    timeout=self.timeout, verify=self.verify,
                    allow_redirects=allow_redirects,
                )
                if resp.status_code in {429, 500, 502, 503, 504}:
                    last_exc = requests.HTTPError(response=resp)
                    time.sleep(self.backoff ** attempt)
                    continue
                resp.raise_for_status()
                ctype = resp.headers.get("Content-Type", "")
                return FetchResponse(
                    url=str(resp.url),
                    status=resp.status_code,
                    content=resp.content,
                    content_type=ctype,
                    headers={k: v for k, v in resp.headers.items()},
                    encoding=resp.encoding,
                )
            except requests.RequestException as exc:
                last_exc = exc
                if attempt + 1 >= self.max_retries:
                    raise
                time.sleep(self.backoff ** attempt)
        raise RuntimeError(f"GET failed: {last_exc}")

    def _throttle(self) -> None:
        wait = self.min_sleep - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()


def browser_headers() -> dict[str, str]:
    return {
        "User-Agent": BROWSER_UA,
        "Accept": "text/html,application/json,text/plain,application/xml,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    }


def bot_headers() -> dict[str, str]:
    return {"User-Agent": BOT_UA, "Accept": "application/json,text/plain,*/*"}
