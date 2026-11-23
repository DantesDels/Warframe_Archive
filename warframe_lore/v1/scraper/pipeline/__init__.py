"""Compatibility shim: pipeline moved to use_cases.pipeline."""

from ..use_cases.pipeline.default import default_pipeline

__all__ = ["default_pipeline"]
