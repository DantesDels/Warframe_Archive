"""ObsidianSynthesizer: hierarchical Micro/Meso/Macro vault synthesis.

Incrementality is driven by the content hash of each note's input
payload; a note whose existing frontmatter carries ``locked: true`` is
never overwritten, whatever changed upstream.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ..blueprint import Blueprint
from ..graph_engine.graph import KnowledgeGraph
from .autolink import autolink
from .frontmatter import render_frontmatter
from .manifest import content_hash, is_locked, load_manifest, save_manifest
from .planning import NotePlan, build_plans
from .ports import VaultExporterPort

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SynthesisReport:
    """Outcome of one synthesis pass, per protection category."""

    written: list[str] = field(default_factory=list)
    up_to_date: list[str] = field(default_factory=list)
    locked: list[str] = field(default_factory=list)


class ObsidianSynthesizer:
    """Render the knowledge graph into an incrementally synced vault."""

    def __init__(self, blueprint: Blueprint, exporter: VaultExporterPort) -> None:
        self.blueprint = blueprint
        self.exporter = exporter

    def _write_plan(
        self, plan: NotePlan, digest: str, graph: KnowledgeGraph
    ) -> None:
        body = (
            autolink(plan.body, graph.entities.values(), plan.self_name)
            if plan.apply_autolink
            else plan.body
        )
        if plan.relative_path.endswith(".canvas"):
            self.exporter.write_note(plan.relative_path, body)
            return
        fields = dict(plan.fields)
        fields["content_hash"] = digest
        fields.setdefault("locked", False)
        self.exporter.write_note(
            plan.relative_path, render_frontmatter(fields) + "\n" + body
        )

    def synthesize(self, graph: KnowledgeGraph) -> SynthesisReport:
        """Write every changed note, skipping up-to-date and locked ones."""
        report = SynthesisReport()
        manifest = load_manifest(self.exporter)
        new_manifest: dict[str, str] = {}
        for plan in build_plans(graph, self.blueprint):
            digest = content_hash(plan.payload)
            existing = self.exporter.read_note(plan.relative_path)
            if existing is not None and is_locked(existing):
                report.locked.append(plan.relative_path)
                if plan.relative_path in manifest:
                    new_manifest[plan.relative_path] = manifest[plan.relative_path]
                continue
            if existing is not None and manifest.get(plan.relative_path) == digest:
                report.up_to_date.append(plan.relative_path)
                new_manifest[plan.relative_path] = digest
                continue
            self._write_plan(plan, digest, graph)
            new_manifest[plan.relative_path] = digest
            report.written.append(plan.relative_path)
        save_manifest(self.exporter, new_manifest)
        logger.info(
            "Vault synced: %d written, %d up-to-date, %d locked",
            len(report.written),
            len(report.up_to_date),
            len(report.locked),
        )
        return report
