"""Default P1 pipeline."""

from __future__ import annotations

from typing import Any

from .runner import PipelineRunner
from .stages_clean import CleanStage
from .stages_dedupe import DedupeStage
from .stages_near_dedupe import NearDedupeStage
from .stages_normalize import NormalizeStage
from .stages_security import SecurityStage


def default_pipeline() -> PipelineRunner:
    stages: list[Any] = [
        NormalizeStage(),
        CleanStage(),
        DedupeStage(),
        NearDedupeStage(),
        SecurityStage(),
    ]
    return PipelineRunner(stages)
