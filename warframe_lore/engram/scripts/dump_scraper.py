"""Readable dump of scraper megafiles (``out/Lore_*.json``) to ``data/raw/``.

Extraction only, no vectorization: allows manual verification of scraped
lore (KIM, Wiki pages) before ingestion/embedding.

Usage (project root):
    python -m warframe_lore.engram.scripts.dump_scraper [--out data/raw]
"""

from __future__ import annotations

import argparse
import json

from ...config import PROJECT_ROOT

# Nickname -> canonical name (wiki title segment / KIM datamine).
HEX = {"Lettie": "Leticia", "Quincy": "Quincy", "Arthur": "Arthur",
       "Amir": "Amir", "Aoi": "Aoi", "Eleanor": "Eleanor"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Local dump of scraped lore.")
    parser.add_argument("--glob", default="out/Lore_*.json",
                        help="Megafile glob pattern (default: out/Lore_*.json)")
    parser.add_argument("--out", default="data/raw",
                        help="Output directory (default: data/raw)")
    args = parser.parse_args()

    out_dir = PROJECT_ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    present = {name: 0 for name in HEX}
    for path in sorted(PROJECT_ROOT.glob(args.glob)):
        data = json.load(open(path, encoding="utf-8"))
        pages = data["pages"]
        target = out_dir / f"{path.stem}.json"
        target.write_text(
            json.dumps(pages, ensure_ascii=False, indent=2), encoding="utf-8")
        for pg in pages:
            title = (pg.get("page_title") or "").lower()
            for nickname, canon in HEX.items():
                if canon.lower() in title:
                    present[nickname] += 1
        print(f"{path.name}: {len(pages)} page(s) -> {target}")

    print("\nHex members presence in dump:")
    for name, count in present.items():
        print(f"  {name:8s} : {count} page(s)")


if __name__ == "__main__":
    main()
