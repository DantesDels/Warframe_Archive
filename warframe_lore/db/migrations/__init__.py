"""Database migrations: one-shot schema/data scripts + tree linking.

* ``dialogue_tree_graph.sql``   — transactional migration that upgrades
  ``kim_dialogues``, adds ``parent_message_id`` to both dialogue tables,
  migrates KIM rows from ``game_dialogues`` and purges them there.
* ``tree_link``                — pure adjacency-list linking heuristic.
* ``link_dialogue_trees``      — runner that applies the heuristic to both
  dialogue tables (executable as ``python -m ...link_dialogue_trees``).
"""
