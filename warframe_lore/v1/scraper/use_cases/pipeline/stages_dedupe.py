"""Pipeline stage: in-run URL dedupe."""

from __future__ import annotations

from .base import PipelineContext, PipelineItem


class DedupeStage:
    name = "dedupe"

    def run(self, items: list[PipelineItem],
            _ctx: PipelineContext) -> list[PipelineItem]:
        seen: set[str] = set()
        for item in items:
            key = str(item.page.url).strip().lower().rstrip("/")
            if key in seen:
                item.accepted = False
                item.reason = "duplicate_url"
            else:
                seen.add(key)
        return items
