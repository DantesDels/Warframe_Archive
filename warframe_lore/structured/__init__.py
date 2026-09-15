"""Structured extraction of the six human-readable element tables.

Each submodule parses one family of pages and returns frozen row
dataclasses ready to be inserted into ``init_db.sql`` tables:

    * ``dialogues``   -> ``game_dialogues``        (KIM, cinematics, quotes)
    * ``fragments``   -> ``lore_items``            (collectibles)
    * ``catalog``     -> ``warframes`` + ``game_quests``  (facade over
      ``warframes``/``quests``)
    * ``news``        -> ``game_updates`` + ``game_announcements``
      (facade over ``updates``/``announcements``)
    * ``rows``/``sites`` -> megafile page -> row-dict mapping
    * ``store``       -> per-page DELETE + INSERT persistence
    * ``pipeline``    -> ETL megafiles -> PostgreSQL (advisory-locked)

The parser modules are pure functions (no I/O): they are unit-testable
without a database.
"""
