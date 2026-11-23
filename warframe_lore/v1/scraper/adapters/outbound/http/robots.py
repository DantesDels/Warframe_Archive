"""Minimal robots.txt and crawl-delay policy (outbound)."""

from __future__ import annotations

from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser


class RobotsPolicy:
    """Caches robots.txt parsers per host."""

    def __init__(self) -> None:
        self._parsers: dict[str, RobotFileParser | None] = {}

    def allowed(self, url: str, user_agent: str) -> bool:
        parser = self._parser_for(url)
        if parser is None:
            return True
        try:
            return parser.can_fetch(user_agent, url)
        except Exception:
            return True

    def crawl_delay(self, url: str, user_agent: str) -> float:
        parser = self._parser_for(url)
        if parser is None:
            return 0.0
        try:
            delay = parser.crawl_delay(user_agent)
            return float(delay) if delay else 0.0
        except Exception:
            return 0.0

    def _parser_for(self, url: str) -> RobotFileParser | None:
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        if base in self._parsers:
            return self._parsers[base]
        rp = RobotFileParser()
        rp.set_url(f"{base}/robots.txt")
        try:
            rp.read()
        except Exception:
            self._parsers[base] = None
            return None
        self._parsers[base] = rp
        return rp
