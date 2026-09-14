"""Graph operations: synthetic anchor and union per character."""

from __future__ import annotations


def _anchor_graph(nodes: list, edges: list, root_label: str,
                  force: bool = True) -> dict:
    """Synthetic anchor for aggregated pages and the existing wiki fallback.

    Native starts stay attached even with a back edge.
    This function is not used for an isolated native conversation.
    """
    if not nodes:
        return {"rootId": None, "nodes": [], "edges": edges}
    roots = {n["id"] for n in nodes} - {e["target"] for e in edges}
    roots.update(n["id"] for n in nodes if n.get("kind") == "start")
    if not force and len(roots) <= 1:
        return {"rootId": next(iter(roots), None), "nodes": nodes,
                "edges": edges}
    root_node = {"id": "root", "kind": "start", "speaker": "",
                 "text": root_label, "player": False, "terminal": False}
    extra = [{"id": f"root:Outgoing:{nid}", "source": "root",
              "target": nid, "label": "", "route": "Outgoing"}
             for nid in sorted(roots) if nid != "root"]
    return {"rootId": "root", "nodes": [root_node] + nodes,
            "edges": edges + extra}


def _merge_graphs(graphs: list[dict]) -> dict:
    """Union of a page's graphs (unique node ids per file)."""
    nodes: list[dict] = []
    edges: list[dict] = []
    seen_nodes: set[str] = set()
    seen_edges: set[str] = set()
    for graph in graphs:
        for node in graph.get("nodes", []):
            if node["id"] not in seen_nodes:
                seen_nodes.add(node["id"])
                nodes.append(node)
        for edge in graph.get("edges", []):
            key = edge["id"]
            if key not in seen_edges:
                seen_edges.add(key)
                edges.append(edge)
    return {"nodes": nodes, "edges": edges}
