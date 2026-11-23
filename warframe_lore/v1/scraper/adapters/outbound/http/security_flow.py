"""URL and payload guards for the outbound HTTP adapter."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ....ports.outbound.events import EventLogPort
from ....security.fetch_policy import FetchPolicy, check_payload, check_url
from ....security.models import ScanResult
from .models import FetchResponse
from .robots import RobotsPolicy


class RequestGuard:
    """Apply URL, robots and payload policy before/after each fetch."""

    def __init__(
        self,
        *,
        policy: FetchPolicy,
        robots: RobotsPolicy,
        event_log: EventLogPort | None,
        quarantine: Any | None,
        reporter: Any,
    ) -> None:
        self.policy = policy
        self.robots = robots
        self.event_log = event_log
        self.quarantine = quarantine
        self.reporter = reporter

    def check_url(self, url: str, headers: Mapping[str, str]) -> None:
        verdict = check_url(url, self.policy)
        if not verdict.allowed:
            self.reject(url, verdict)
        user_agent = str(headers.get("User-Agent", "*"))
        if not self.robots.allowed(url, user_agent):
            self.reject(
                url, ScanResult(False, "Bloqué par robots.txt.", "blocked_robots", url)
            )

    def check_payload(self, response: FetchResponse) -> None:
        verdict = check_payload(
            response.url, response.content, response.content_type, self.policy
        )
        if verdict.allowed:
            return
        if self.quarantine is not None:
            self.quarantine.put(
                response.url, response.content, verdict.reason, verdict.code
            )
        self.reject(response.url, verdict)

    def reject(self, url: str, verdict: ScanResult) -> None:
        self.reporter.skip(verdict.code, url)
        if self.event_log is not None:
            self.event_log.emit(
                "security_blocked", url=url, code=verdict.code, reason=verdict.reason
            )
        raise PermissionError(f"{verdict.code}: {verdict.reason}")
