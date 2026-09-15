"""Tests for the dialogue tree linking heuristic (pure, no DB needed)."""

from warframe_lore.db.migrations.tree_link import link_dialogue_parents


class TestSequentialLink:
    """Default rule: previous node becomes the current node's parent."""

    def test_single_message_is_root(self):
        rows = [(0, 1, False)]
        assert link_dialogue_parents(rows) == {1: None}

    def test_two_sequential_messages(self):
        rows = [(0, 1, False), (1, 2, False)]
        assert link_dialogue_parents(rows) == {1: None, 2: 1}

    def test_three_sequential_messages(self):
        rows = [(0, 1, False), (1, 2, False), (2, 3, False)]
        assert link_dialogue_parents(rows) == {1: None, 2: 1, 3: 2}

    def test_unsorted_input_is_sorted_by_message_order(self):
        rows = [(2, 3, False), (0, 1, False), (1, 2, False)]
        assert link_dialogue_parents(rows) == {1: None, 2: 1, 3: 2}


class TestChoiceBranching:
    """player_choice=True lines branch from the NPC parent, not each other."""

    def test_single_choice_after_npc(self):
        rows = [(0, 1, False), (1, 2, True)]
        assert link_dialogue_parents(rows) == {1: None, 2: 1}

    def test_consecutive_choices_share_the_npc_parent(self):
        rows = [(0, 1, False), (1, 2, True), (2, 3, True)]
        result = link_dialogue_parents(rows)
        assert result[2] == 1
        assert result[3] == 1

    def test_three_consecutive_choices_share_the_same_npc_parent(self):
        rows = [(0, 1, False), (1, 2, True), (2, 3, True), (3, 4, True)]
        result = link_dialogue_parents(rows)
        assert result[2] == 1
        assert result[3] == 1
        assert result[4] == 1

    def test_npc_reply_after_choices_stays_sequential(self):
        rows = [(0, 1, False), (1, 2, True), (2, 3, True), (3, 4, False)]
        result = link_dialogue_parents(rows)
        assert result == {1: None, 2: 1, 3: 1, 4: 3}

    def test_choice_blocks_separated_by_an_npc_reply(self):
        rows = [
            (0, 1, False),   # NPC A
            (1, 2, True),    # choice C1 -> A
            (2, 3, False),   # NPC reply -> C1 (sequential)
            (3, 4, True),    # choice C2 -> NPC reply (branch on it)
            (4, 5, False),   # NPC reply -> C2 (sequential)
        ]
        result = link_dialogue_parents(rows)
        assert result[2] == 1
        assert result[4] == 3
        assert result[5] == 4

    def test_leading_choice_without_npc_is_root(self):
        rows = [(0, 1, True), (1, 2, False)]
        result = link_dialogue_parents(rows)
        assert result[1] is None
        assert result[2] == 1

    def test_choice_block_reuses_the_last_npc_after_messages(self):
        rows = [
            (0, 1, False),   # NPC A
            (1, 2, False),   # NPC B
            (2, 3, True),    # choice -> B
            (3, 4, True),    # choice -> B (same base, not the 1st choice)
        ]
        result = link_dialogue_parents(rows)
        assert result[3] == 2
        assert result[4] == 2
