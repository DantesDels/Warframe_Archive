-- ============================================================================
-- Migration: drop redundant columns from kim_dialogues
--
-- kim_dialogues is the dedicated KIM table; these columns are unused or
-- implied:
--   - dialogue_kind  : always 'kim' for this table;
--   - timestamp      : legacy degraded-parser metadata, never used by the
--                      structured pipeline or the RAG renderer;
--   - created_at     : audit timestamp not needed for dialogue messages.
--
-- Transactional and idempotent (DROP COLUMN IF EXISTS).
--
-- Usage:
--   psql -U <user> -d warframe_lore -f drop_kim_unused_columns.sql
-- ============================================================================

BEGIN;

ALTER TABLE kim_dialogues
    DROP COLUMN IF EXISTS dialogue_kind,
    DROP COLUMN IF EXISTS timestamp,
    DROP COLUMN IF EXISTS created_at;

COMMIT;