"""HTTP header profiles for outbound requests."""

from __future__ import annotations

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 AtelierV1/1.0"
)
BOT_UA = "AtelierV1/1.0 (+local data collection; contact: local)"


def browser_headers() -> dict[str, str]:
    return {
        "User-Agent": BROWSER_UA,
        "Accept": "text/html,application/json,text/plain,application/xml,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    }


def bot_headers() -> dict[str, str]:
    return {"User-Agent": BOT_UA, "Accept": "application/json,text/plain,*/*"}
