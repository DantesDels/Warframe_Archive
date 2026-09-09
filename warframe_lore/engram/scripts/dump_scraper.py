"""Dump lisible des megafiles du scraper (``out/Lore_*.json``) vers ``data/raw/``.

Extraction uniquement, aucune vectorisation : permet de vérifier manuellement
le lore scrapé (KIM, pages Wiki) avant ingestion/embedding.

Utilisation (racine du projet) :
    python -m warframe_lore.engram.scripts.dump_scraper [--out data/raw]
"""

from __future__ import annotations

import argparse
import json

from ...config import PROJECT_ROOT

# Surnom -> nom canonique (segment de titre wiki / datamine KIM).
HEX = {"Lettie": "Leticia", "Quincy": "Quincy", "Arthur": "Arthur",
       "Amir": "Amir", "Aoi": "Aoi", "Eleanor": "Eleanor"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Dump local du lore scrapé.")
    parser.add_argument("--glob", default="out/Lore_*.json",
                        help="Motif des megafiles (défaut: out/Lore_*.json)")
    parser.add_argument("--out", default="data/raw",
                        help="Dossier de sortie (défaut: data/raw)")
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

    print("\nPrésence des membres des Hex dans le dump :")
    for name, count in present.items():
        print(f"  {name:8s} : {count} page(s)")


if __name__ == "__main__":
    main()