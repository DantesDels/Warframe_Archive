"""CLI entrypoint for generic declarative JSON/GitHub collection presets."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from .service import run_preset_collection

_V1_ROOT = Path(__file__).resolve().parents[2]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a declarative JSON/GitHub collection preset."
    )
    parser.add_argument(
        "--preset",
        required=True,
        help="Path to the YAML or JSON collection preset file.",
    )
    parser.add_argument(
        "--manifest",
        default=str(_V1_ROOT / "data" / "v1" / "json_collection_manifest.json"),
        help="Path to the local incremental manifest file.",
    )
    parser.add_argument(
        "--output-dir",
        default="",
        help="Optional directory to write enriched JSON documents.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bypass manifest sha/ETag checks and reprocess all resources.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_preset_collection(
        args.preset,
        manifest_path=args.manifest,
        force=bool(args.force),
    )
    if args.output_dir:
        out_root = Path(args.output_dir)
        out_root.mkdir(parents=True, exist_ok=True)
        for doc in result.documents:
            (out_root / doc.name).write_text(
                json.dumps(doc.data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
    return 0 if not result.errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
