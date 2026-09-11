"""Blueprint script: write ``timelineData.json`` (flat graph fixture).

Regenerate the mock/contract fixture from the curated data::

    python -m warframe_lore.timeline._dump_json

Outputs ``warframe_lore/timeline/timelineData.json``, the flat
``{nodes, edges}`` contract consumed by the frontend mock reader.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import graph_payload

_OUT = Path(__file__).resolve().parent / "timelineData.json"


def main() -> None:
    payload = graph_payload()
    _OUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        f"timelineData.json : {len(payload['nodes'])} nœuds, "
        f"{len(payload['edges'])} arêtes -> {_OUT}",
    )


if __name__ == "__main__":
    main()