"""Structured extraction of the six human-readable element tables.

Each parser in the ``parsers`` subpackage owns one family of pages and
returns frozen row dataclasses ready to be inserted into ``init_db.sql``
tables:

    * ``parsers/dialogues``     -> ``game_dialogues`` (KIM, cinematics, quotes)
    * ``parsers/fragments``     -> ``lore_items`` (collectibles)
    * ``parsers/warframes``     -> ``warframes``
    * ``parsers/quests``        -> ``game_quests``
    * ``parsers/updates``       -> ``game_updates``
    * ``parsers/announcements`` -> ``game_announcements``
    * ``catalog``/``news``      -> public facades over those parsers
    * ``rows``/``sites``        -> megafile page -> row-dict mapping
    * ``rendering``             -> row values -> (title, content) for embedding
    * ``store``                 -> per-page DELETE + INSERT persistence
    * ``pipeline``              -> ETL megafiles -> PostgreSQL (advisory-locked)

The parser modules are pure functions (no I/O): they are unit-testable
without a database.
"""
