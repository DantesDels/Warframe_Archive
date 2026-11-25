"""Graph analysis: centrality pivots, communities and cross-arc bridges.

Pure Python (no graph dependency): degree centrality plus deterministic
greedy modularity community detection, suitable for entity-scale graphs.
"""

from __future__ import annotations

from collections import Counter

from .graph import Community, GraphAnalysis, KnowledgeGraph


def _adjacency(graph: KnowledgeGraph) -> dict[str, Counter[str]]:
    adjacency: dict[str, Counter[str]] = {eid: Counter() for eid in graph.entities}
    for relation in graph.relations:
        source, target = relation.source_id_entity, relation.target_id_entity
        if source in adjacency and target in adjacency:
            adjacency[source][target] += 1
            adjacency[target][source] += 1
    return adjacency


def _centrality(adjacency: dict[str, Counter[str]]) -> dict[str, float]:
    total = len(adjacency)
    if total <= 1:
        return {eid: 0.0 for eid in adjacency}
    return {
        eid: sum(neighbors.values()) / (total - 1)
        for eid, neighbors in adjacency.items()
    }


def _detect_communities(adjacency: dict[str, Counter[str]]) -> dict[str, int]:
    """Greedy modularity optimization (Louvain first phase, deterministic).

    Label propagation collapses to one cluster on small bridged graphs;
    modularity keeps densely linked groups separated by sparse bridges.
    """
    nodes = sorted(adjacency)
    degree = {node: sum(adjacency[node].values()) for node in nodes}
    total_weight = sum(degree.values()) / 2
    if total_weight == 0:
        return {node: index for index, node in enumerate(nodes)}
    community = {node: index for index, node in enumerate(nodes)}
    while True:
        totals: dict[int, float] = {}
        for node in nodes:
            label = community[node]
            totals[label] = totals.get(label, 0) + degree[node]
        moved = False
        for node in nodes:
            own = community[node]
            weights: dict[int, float] = {}
            for neighbor, weight in adjacency[node].items():
                label = community[neighbor]
                weights[label] = weights.get(label, 0) + weight
            best_label = own
            best_gain = weights.get(own, 0) - (
                (totals[own] - degree[node]) * degree[node] / (2 * total_weight)
            )
            for label, weight_in in sorted(weights.items()):
                if label == own:
                    continue
                gain = weight_in - totals[label] * degree[node] / (2 * total_weight)
                if gain > best_gain + 1e-12:
                    best_label, best_gain = label, gain
            if best_label != own:
                totals[own] -= degree[node]
                totals[best_label] = totals.get(best_label, 0) + degree[node]
                community[node] = best_label
                moved = True
        if not moved:
            break
    return community


def _community_label(
    graph: KnowledgeGraph, member_ids: list[str], centrality: dict[str, float]
) -> str:
    arcs: Counter[str] = Counter()
    members = set(member_ids)
    for entity_id in member_ids:
        entity = graph.entities.get(entity_id)
        if entity:
            arcs.update(f.arc_or_context for f in entity.facts if f.arc_or_context)
    for relation in graph.relations:
        if (
            relation.source_id_entity in members
            and relation.target_id_entity in members
        ):
            if relation.arc_or_context:
                arcs[relation.arc_or_context] += 1
    if arcs:
        return min(arcs, key=lambda arc: (-arcs[arc], arc))
    pivot = max(member_ids, key=lambda eid: (centrality.get(eid, 0.0), eid))
    return graph.entities[pivot].name


def analyze(graph: KnowledgeGraph) -> GraphAnalysis:
    """Compute centrality, detect communities and cross-community bridges."""
    adjacency = _adjacency(graph)
    centrality = _centrality(adjacency)
    labels = _detect_communities(adjacency)
    groups: dict[int, list[str]] = {}
    for entity_id, label in labels.items():
        groups.setdefault(label, []).append(entity_id)
    communities = [
        Community(
            id=idx,
            label=_community_label(graph, sorted(members), centrality),
            entity_ids=sorted(members),
        )
        for idx, (_label, members) in enumerate(sorted(groups.items()))
    ]
    community_of = {eid: c.id for c in communities for eid in c.entity_ids}
    bridges = [
        relation
        for relation in graph.relations
        if community_of.get(relation.source_id_entity)
        != community_of.get(relation.target_id_entity)
    ]
    return GraphAnalysis(
        centrality=centrality, communities=communities, bridges=bridges
    )
