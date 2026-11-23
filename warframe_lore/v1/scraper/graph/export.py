"""Export graph data and an offline HTML visualization."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .html_template import HTML_TEMPLATE


def export_graph(out_dir: Path, graph: dict[str, Any]) -> list[Path]:
    """Write graph.json and graph.html and return the created paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "graph.json"
    html_path = out_dir / "graph.html"
    json_path.write_text(
        json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    payload = json.dumps(graph, ensure_ascii=False)
    html_path.write_text(
        HTML_TEMPLATE.replace("__GRAPH_DATA__", payload), encoding="utf-8"
    )
    return [json_path, html_path]
