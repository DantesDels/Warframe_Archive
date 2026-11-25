"""Unified CLI for the downstream pipeline: GraphEngine then Synthesizer.

Usage:
    python -m warframe_lore.v1.aval_cli --export-dir <run dir> \
        --blueprint <blueprint.yaml> --store-dir <graph dir> --vault-dir <vault>
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .blueprint import load_blueprint
from .graph_engine.engine import GraphEngine
from .graph_engine.json_store import JsonGraphStore
from .scraper.adapters.outbound.llm.openai_compat import OpenAiCompatLlmAdapter
from .scraper.capabilities.models import LlmBudget
from .synthesizer.synthesizer import ObsidianSynthesizer
from .synthesizer.vault import ObsidianVaultExporter


def main(argv: list[str] | None = None) -> int:
    """Run both downstream stages on one Scraper v1 export directory."""
    parser = argparse.ArgumentParser(
        description="Pipeline aval : knowledge graph puis vault Obsidian."
    )
    parser.add_argument("--export-dir", required=True, type=Path)
    parser.add_argument("--blueprint", required=True, type=Path)
    parser.add_argument("--store-dir", required=True, type=Path)
    parser.add_argument("--vault-dir", required=True, type=Path)
    parser.add_argument("--endpoint", default="http://127.0.0.1:1234/v1")
    parser.add_argument("--model", default="")
    parser.add_argument("--max-calls", type=int, default=200)
    parser.add_argument("--max-tokens", type=int, default=100_000)
    parser.add_argument("--batch-size", type=int, default=3)
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    blueprint = load_blueprint(args.blueprint)
    budget = LlmBudget(
        enabled=True,
        endpoint=args.endpoint,
        model=args.model,
        max_calls=args.max_calls,
        max_tokens=args.max_tokens,
    )
    engine = GraphEngine(
        blueprint,
        OpenAiCompatLlmAdapter(budget),
        JsonGraphStore(args.store_dir),
        batch_size=args.batch_size,
    )
    graph = engine.run(args.export_dir)
    synthesizer = ObsidianSynthesizer(blueprint, ObsidianVaultExporter(args.vault_dir))
    report = synthesizer.synthesize(graph)
    print(
        f"Graphe : {len(graph.entities)} entités, {len(graph.relations)} relations. "
        f"Vault : {len(report.written)} notes écrites, "
        f"{len(report.up_to_date)} à jour, {len(report.locked)} verrouillées."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
