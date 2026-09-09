"""CLI entrypoint: ``python -m warframe_lore.rag_extract <url> [...]``.

Outputs the extracted ``LoreChunk`` records as JSON.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from typing import Any, Dict, Iterable, Sequence

from warframe_lore.rag_extract import (
    BaseExtractor,
    MediaWikiExtractor,
    PlaywrightFallbackExtractor,
    run_pipeline,
)


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="warframe_lore.rag_extract",
        description="Pipeline d'extraction RAG découplé (Wikitext API + "
        "fallback Playwright) pour la base vectorielle.",
    )
    parser.add_argument(
        "urls",
        nargs="+",
        help="URLs Fandom (ou titres de page) à extraire.",
    )
    parser.add_argument(
        "--strategy",
        choices=("auto", "wiki", "playwright"),
        default="auto",
        help="auto: Wikitext puis fallback DOM; wiki: Wikitext seul; "
        "playwright: DOM seul.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=3,
        help="Requêtes concurrentes (sémaphore).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Fichier JSON de sortie (défaut: stdout).",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Logs INFO sur stderr."
    )
    return parser.parse_args(argv)


def _strategy(args: argparse.Namespace) -> tuple[BaseExtractor, BaseExtractor | None]:
    wiki = MediaWikiExtractor()
    dom = PlaywrightFallbackExtractor()
    if args.strategy == "wiki":
        return wiki, None
    if args.strategy == "playwright":
        return dom, None
    return wiki, dom


def _chunks_payload(chunks: Iterable[Any]) -> list[Dict[str, Any]]:
    return [chunk.to_payload() for chunk in chunks]


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(list(argv) if argv is not None else sys.argv[1:])
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:  # pragma: no cover - older Python without reconfigure
        pass
    primary, fallback = _strategy(args)
    urls = [
        url if "://" in url else f"https://warframe.fandom.com/wiki/{url}"
        for url in args.urls
    ]

    chunks = asyncio.run(
        run_pipeline(
            urls,
            primary=primary,
            fallback=fallback,
            concurrency=args.concurrency,
        )
    )
    payload = {
        "pages": urls,
        "total_chunks": len(chunks),
        "chunks": _chunks_payload(chunks),
    }
    serialized = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(serialized + "\n")
    else:
        print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())