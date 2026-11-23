"""Pipeline stage: normalize collected page text."""

from __future__ import annotations

from .base import PipelineContext, PipelineItem


class NormalizeStage:
    name = "normalize"

    def run(self, items: list[PipelineItem],
            _ctx: PipelineContext) -> list[PipelineItem]:
        for item in items:
            page = item.page
            text = (page.content or "").replace("\r", "")
            lines = [" ".join(line.split()) for line in text.splitlines()]
            page.content = "\n".join(line for line in lines if line)
            if not page.content.strip():
                item.accepted = False
                item.reason = "contenu vide"
        return items
