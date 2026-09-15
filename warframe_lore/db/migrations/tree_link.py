"""Pure adjacency-list heuristic: one dialogue group -> parent links.

Zero dependencies: takes ``(message_order, node_id, player_choice)`` rows and
returns a ``{node_id: parent_id_or_None}`` mapping, fully testable without a
database.  See :func:`link_dialogue_parents` for the branching rules.
"""

from __future__ import annotations

from collections.abc import Sequence


def link_dialogue_parents(
    rows: Sequence[tuple[int, int, bool]],
) -> dict[int, int | None]:
    """Compute ``parent_message_id`` for one dialogue group.

    ``rows`` is a sequence of ``(message_order, node_id, player_choice)``
    tuples.  The heuristic follows the user contract:

    * **Sequential link** — the previous node becomes the current node's
      parent (default rule).
    * **Branching** — consecutive ``player_choice = True`` lines all branch
      from the same NPC parent message (the last non-choice line) instead of
      chaining one choice to the previous one.

    Rows are sorted by ``message_order`` defensively (stable sort).

    Returns ``{node_id: parent_id_or_None}``; the first node of a group (or a
    leading choice block with no NPC message) maps to ``None``.
    """
    ordered = sorted(rows, key=lambda row: row[0])
    parents: dict[int, int | None] = {}
    previous_id: int | None = None
    choice_base_id: int | None = None
    in_choice_block = False

    for _message_order, node_id, is_choice in ordered:
        if is_choice:
            if not in_choice_block:
                # First choice of a block: open the branch from the last NPC
                # message; consecutive choices below reuse the same base.
                choice_base_id = previous_id
                in_choice_block = True
            parents[node_id] = choice_base_id
        else:
            # NPC message: sequential link to the previous node, and it
            # becomes the branch base for any upcoming choice block.
            parents[node_id] = previous_id
            in_choice_block = False
        previous_id = node_id

    return parents


__all__ = ["link_dialogue_parents"]
