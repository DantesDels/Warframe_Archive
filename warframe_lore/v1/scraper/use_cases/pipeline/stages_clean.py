"""Pipeline stage: clean and compact normalized content."""

from __future__ import annotations

from .base import PipelineContext, PipelineItem


class CleanStage:
    name = "clean"

    def run(self, items: list[PipelineItem],
            _ctx: PipelineContext) -> list[PipelineItem]:
        for item in items:
            if not item.accepted:
                continue
            text = item.page.content
            text = "\n".join(line.rstrip() for line in text.splitlines())
            while "\n\n\n" in text:
                text = text.replace("\n\n\n", "\n\n")
            item.page.content = text.strip()
            if not item.page.content:
                item.accepted = False
                item.reason = "contenu vide apres nettoyage"
        return items
