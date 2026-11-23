"""Pipeline stage: fetch-time security check."""

from __future__ import annotations

from ...security.fetch_policy import check_payload
from .base import PipelineContext, PipelineItem


class SecurityStage:
    name = "security"

    def run(self, items: list[PipelineItem],
            _ctx: PipelineContext) -> list[PipelineItem]:
        for item in items:
            raw = item.page.raw or item.page.content.encode("utf-8")
            verdict = check_payload(item.page.url, raw, item.page.content_type)
            if not verdict.allowed:
                item.accepted = False
                item.reason = verdict.reason
        return items
