"""Run pipeline stages sequentially."""

from __future__ import annotations

from .base import PipelineContext, PipelineItem, Stage


class PipelineRunner:
    def __init__(self, stages: list[Stage] | None = None) -> None:
        self.stages = list(stages or [])

    def run(self, items: list[PipelineItem],
            ctx: PipelineContext) -> list[PipelineItem]:
        current = items
        for stage in self.stages:
            current = stage.run(current, ctx)
            current = [item for item in current if item.accepted]
        return current
