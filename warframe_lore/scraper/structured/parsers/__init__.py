"""Pure parsers for the human-readable element pages.

Each module owns one family of pages and returns frozen row dataclasses
(no I/O), so they stay unit-testable without a database:

    * ``dialogues``     -> ``game_dialogues`` / ``kim_dialogues``;
    * ``fragments``     -> ``lore_items``;
    * ``warframes``     -> ``warframes``;
    * ``quests``        -> ``game_quests``;
    * ``updates``       -> ``game_updates``;
    * ``announcements`` -> ``game_announcements``.

The ``catalog`` and ``news`` facades at the package root re-export these
parsers to keep their historical import paths stable.
"""
