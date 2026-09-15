-- ============================================================================
-- Dialogue tree graph migration — kim_dialogues upgrade + KIM data transfer
--
-- One transaction that:
--   1. adds a self-referential parent_message_id (adjacency list, ON DELETE
--      SET NULL) to BOTH game_dialogues and kim_dialogues;
--   2. upgrades kim_dialogues with the columns it lacks versus game_dialogues
--      (dialogue_kind, context, chapter, chemistry_gain);
--   3. migrates the KIM rows out of game_dialogues into kim_dialogues via an
--      UPSERT on UNIQUE (wiki_page_id, message_order): twin rows are upgraded
--      with the authoritative parse, non-twin rows receive fresh sequence ids
--      (no PRIMARY KEY conflict), and existing kim_dialogues ids survive;
--   4. purges the migrated KIM rows from game_dialogues.
--
-- Idempotent: safe to re-run against a partially migrated database.
--
-- Usage:
--   psql -U <user> -d warframe_lore -f dialogue_tree_graph.sql
-- ============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Graph capability: self-referential foreign key on both tables.
--    ON DELETE SET NULL: removing a message orphans its children (they become
--    roots) instead of cascade-deleting the whole branch.
-- ---------------------------------------------------------------------------
ALTER TABLE game_dialogues
    ADD COLUMN IF NOT EXISTS parent_message_id BIGINT
        REFERENCES game_dialogues (id) ON DELETE SET NULL;

ALTER TABLE kim_dialogues
    ADD COLUMN IF NOT EXISTS parent_message_id BIGINT
        REFERENCES kim_dialogues (id) ON DELETE SET NULL;

-- Graph traversal index: WHERE parent_message_id = <node> maps children.
CREATE INDEX IF NOT EXISTS idx_dialogues_parent
    ON game_dialogues (parent_message_id);
CREATE INDEX IF NOT EXISTS idx_kim_parent
    ON kim_dialogues (parent_message_id);

-- ---------------------------------------------------------------------------
-- 2. kim_dialogues schema upgrade: mirror the game_dialogues columns.
--    dialogue_kind defaults to 'kim' with the same CHECK as game_dialogues so
--    the degraded ingest path (replace_dialogues) keeps inserting.
-- ---------------------------------------------------------------------------
ALTER TABLE kim_dialogues
    ADD COLUMN IF NOT EXISTS dialogue_kind TEXT NOT NULL DEFAULT 'kim'
        CHECK (dialogue_kind IN ('kim', 'cinematic', 'quote')),
    ADD COLUMN IF NOT EXISTS context TEXT,
    ADD COLUMN IF NOT EXISTS chapter TEXT,
    ADD COLUMN IF NOT EXISTS chemistry_gain BOOLEAN NOT NULL DEFAULT FALSE;

-- ---------------------------------------------------------------------------
-- 3. Migrate the KIM rows from game_dialogues into kim_dialogues.
--
-- UNIQUE (wiki_page_id, message_order) exists on BOTH tables, so a raw INSERT
-- would violate it for the 20 522 overlapping rows: UPSERT upgrades each twin
-- with the enriched game_dialogues values (the two tables parsed the same 14
-- KIM pages with different parsers).  The few kim_dialogues-only rows (13)
-- keep their own content, and new ids come from the kim_dialogues sequence —
-- no id reassignment, no PRIMARY KEY conflict.
-- ---------------------------------------------------------------------------
INSERT INTO kim_dialogues (
    wiki_page_id, message_order, speaker, message_text,
    player_choice, chemistry_gain, dialogue_kind, context, chapter
)
SELECT
    wiki_page_id, message_order, speaker, message_text,
    player_choice, chemistry_gain, dialogue_kind, context, chapter
FROM game_dialogues
WHERE dialogue_kind = 'kim'
ON CONFLICT (wiki_page_id, message_order) DO UPDATE SET
    speaker        = EXCLUDED.speaker,
    message_text   = EXCLUDED.message_text,
    player_choice  = EXCLUDED.player_choice,
    chemistry_gain = EXCLUDED.chemistry_gain,
    dialogue_kind  = EXCLUDED.dialogue_kind,
    context        = EXCLUDED.context,
    chapter        = EXCLUDED.chapter;

-- ---------------------------------------------------------------------------
-- 4. Purge the migrated rows: game_dialogues becomes KIM-free.
-- ---------------------------------------------------------------------------
DELETE FROM game_dialogues WHERE dialogue_kind = 'kim';

COMMIT;