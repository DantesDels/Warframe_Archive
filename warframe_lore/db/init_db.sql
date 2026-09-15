-- ============================================================================
-- WARFRAME "Cephalon Archive" — Schéma de base de données (Phase 2 : SQL)
--
-- Objectif : remplacer le stockage JSON plat par une base PostgreSQL
-- normalisée (3NF), préparée pour le RAG et le support vectoriel (pgvector).
--
-- Ce fichier est le DDL source de vérité des tables.  Les modèles SQLAlchemy
-- (warframe_lore/db/models.py) doivent rester synchronisés avec lui.
--
-- Exécution :
--   psql -U <user> -d warframe_lore -f init_db.sql
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 0. Extensions (requises pour le RAG / embeddings / recherche lexicale).
--    - vector          : type vector(n) et opérateurs cosine (<=>).
--    - pg_trgm         : index trigrammes -> accélère ``ILIKE '%token%'`` des
--                        titres (suggest_title) et le matching flou.
-- ----------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ----------------------------------------------------------------------------
-- 1. Table wiki_pages : racine d'une page de wiki.
--    Une ligne par page (identifiée par son page_id wiki natif).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS wiki_pages (
    page_id            BIGINT PRIMARY KEY,          -- pageid natif Wiki
    page_title         TEXT        NOT NULL,        -- titre exact de la page
    category           TEXT        NOT NULL,        -- bucket logique (ex: Lore_Quetes)
    namespace          INT         NOT NULL DEFAULT 0, -- espace de noms Wiki (0 = contenu)
    last_updated       TIMESTAMPTZ,                 -- timestamp dernière révision wiki
    touched            TEXT,                        -- date "touched" brute de l'API
    canon_status       TEXT        NOT NULL DEFAULT 'canon'
                       CHECK (canon_status IN ('canon', 'speculation', 'community_theory')),
    source_url         TEXT,                        -- URL canonique de la page
    content_markdown   TEXT,                        -- contenu nettoyé complet (ref. RAG)
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Mise à niveau additive pour les bases créées avant l'ajout de ces colonnes.
ALTER TABLE wiki_pages ADD COLUMN IF NOT EXISTS namespace INT NOT NULL DEFAULT 0;
ALTER TABLE wiki_pages ADD COLUMN IF NOT EXISTS content_markdown TEXT;

-- Index pour retrouver rapidement une page par titre et par bucket.
CREATE UNIQUE INDEX IF NOT EXISTS idx_wiki_pages_title   ON wiki_pages (page_title);
CREATE INDEX        IF NOT EXISTS idx_wiki_pages_bucket  ON wiki_pages (category);
CREATE INDEX        IF NOT EXISTS idx_wiki_pages_canon   ON wiki_pages (canon_status);
-- Trigrammes : rend le ``ILIKE '%token%'`` du suggest_title indexé en GIN
-- (sinon balayage séquentiel de toutes les pages à chaque requête).
CREATE INDEX IF NOT EXISTS idx_wiki_pages_title_trgm    ON wiki_pages
    USING GIN (page_title gin_trgm_ops);

-- ----------------------------------------------------------------------------
-- 2. Table lore_chunks : paragraphes/sections découpés du contenu nettoyé.
--    Évite de stocker des textes kilométriques dans une seule cellule et
--    prépare le RAG : chaque chunk porte son embedding vectoriel.
--
--    Une page -> N chunks (chunk_index 0..N-1), ordonnés.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS lore_chunks (
    id                BIGSERIAL PRIMARY KEY,
    wiki_page_id      BIGINT      NOT NULL
                      REFERENCES wiki_pages (page_id) ON DELETE CASCADE,
    chunk_index       INT         NOT NULL,          -- position dans la page (0-based)
    content_markdown  TEXT        NOT NULL,          -- texte nettoyé du chunk
    -- Métadonnées du chunk (Phase 2.5) : hiérarchie Markdown (Header 1/2/3)
    -- et locuteurs pour les dialogues.  Permet au RAG de filtrer AVANT la
    -- recherche vectorielle (ex: tous les chunks d'un même chapitre, ou
    -- d'une scène précise).
    metadata          JSONB       NOT NULL DEFAULT '{}'::jsonb,
    -- Dimension 1024 = vecteur réel renvoyé par le modèle d'embedding
    -- BGE-M3 GGUF ("baai-bge-m3-568m", servi par LM Studio).
    embedding         vector(1024),                   -- vecteur sémantique (nullable)
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (wiki_page_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_chunks_page ON lore_chunks (wiki_page_id);
CREATE INDEX IF NOT EXISTS idx_chunks_metadata ON lore_chunks USING GIN (metadata);
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON lore_chunks
    USING hnsw (embedding vector_cosine_ops);
-- Index GIN sur l'expression tsvector des chunks : c'est EXACTEMENT
-- l'expression interrogée par le canal full-text (websearch_to_tsquery),
-- donc l'index est utilisé au lieu d'un seq scan sur tout le corpus.
CREATE INDEX IF NOT EXISTS idx_chunks_fts ON lore_chunks
    USING GIN (to_tsvector('french', content_markdown));

-- ----------------------------------------------------------------------------
-- 3. Table kim_dialogues : discussions KIM ("Kinemantik Instant Messenger"),
--    formatées ligne par ligne (message = une ligne : locuteur + texte).
--
--    Reprend le format parsé de nos requêtes API ʼKinemantik Instant Messengerʼ.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS kim_dialogues (
    id                BIGSERIAL PRIMARY KEY,
    wiki_page_id      BIGINT      NOT NULL
                      REFERENCES wiki_pages (page_id) ON DELETE CASCADE,
    message_order     INT         NOT NULL,          -- ordre chronologique du message
    speaker           TEXT        NOT NULL,          -- locuteur (ex: "Amir")
    message_text      TEXT        NOT NULL,          -- contenu du message
    player_choice     BOOLEAN     NOT NULL DEFAULT FALSE,
    timestamp         TEXT,                          -- heure du message si disponible
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (wiki_page_id, message_order)
);

-- Mise à niveau additive : distinction des choix du joueur.
ALTER TABLE kim_dialogues ADD COLUMN IF NOT EXISTS player_choice BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_kim_page ON kim_dialogues (wiki_page_id);

-- ----------------------------------------------------------------------------
-- 4. Table game_entities_i18n : entités du jeu localisées (Warframe Public
--    Export).  Une ligne par couple (entité, langue) ; ``name``/``description``
--    proviennent des fichiers JSON des manifests officiels (index_<lang>).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS game_entities_i18n (
    id                BIGSERIAL PRIMARY KEY,
    entity_id         TEXT        NOT NULL,          -- uniqueName du jeu (ex: "/Lotus/...")
    entity_type       TEXT,                          -- type (Items/Recipes/Ships...)
    lang              TEXT        NOT NULL DEFAULT 'en',
    name              TEXT        NOT NULL,
    description       TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (entity_id, lang)
);

CREATE INDEX IF NOT EXISTS idx_entities_lang ON game_entities_i18n (lang);
CREATE INDEX IF NOT EXISTS idx_entities_type ON game_entities_i18n (entity_type);

-- ----------------------------------------------------------------------------
-- 5. Table sync_state : historique de synchronisation (remplace sync_state.json).
--    Stocke, par bucket, le dernier 'touched' vu pour chaque page, pour le
--    mode delta : on compare le touched de l'API à celui stocké ici.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sync_state (
    bucket_id     TEXT        NOT NULL,              -- ex: 'Lore_Quetes'
    page_title    TEXT        NOT NULL,
    page_id       BIGINT      NOT NULL,
    touched       TEXT,                              -- last 'touched' vu
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (bucket_id, page_title)
);

CREATE INDEX IF NOT EXISTS idx_sync_bucket ON sync_state (bucket_id);

-- ----------------------------------------------------------------------------
-- 6. Table game_dialogues : dialogues structurés, ligne par ligne, avec des
--    balises de contexte pour la lecture humaine.
--    - dialogue_kind  : 'kim' (Kinemantik Instant Messenger), 'cinematic'
--                       (transcript de quête), 'quote' (citations vocales) ;
--    - context        : balise parente (quête pour les cinématiques, personnage
--                       pour KIM et les citations) ;
--    - chapter        : titre du chapitre '##' où la ligne apparaît.
--    Pour KIM, chemistry_gain reprend le marqueur '{Convo ends.}' (gain de
--    chemistry invisible en jeu) : le texte brut est conservé, le marqueur
--    est promu en booléen lisible.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS game_dialogues (
    id                BIGSERIAL PRIMARY KEY,
    wiki_page_id      BIGINT      NOT NULL
                      REFERENCES wiki_pages (page_id) ON DELETE CASCADE,
    dialogue_kind     TEXT        NOT NULL
                      CHECK (dialogue_kind IN ('kim', 'cinematic', 'quote')),
    context           TEXT,                           -- quête / personnage
    chapter           TEXT,                           -- chapitre '##' de la scène
    speaker           TEXT        NOT NULL,           -- locuteur / narrateur
    message_text      TEXT        NOT NULL,           -- texte du message
    player_choice     BOOLEAN     NOT NULL DEFAULT FALSE,
    chemistry_gain    BOOLEAN     NOT NULL DEFAULT FALSE,
    message_order     INT         NOT NULL,           -- ordre dans la page
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (wiki_page_id, message_order)
);

CREATE INDEX IF NOT EXISTS idx_dialogues_page ON game_dialogues (wiki_page_id);
CREATE INDEX IF NOT EXISTS idx_dialogues_kind ON game_dialogues (dialogue_kind);

-- ----------------------------------------------------------------------------
-- 7. Table lore_items : collectibles de lore trouvés en jeu (fragments,
--    parchemins, enregistrements audio), avec leur auteur et leur lieu.
--    - series      : catégorie de la série (ex: 'Glass Shard Fragments') ;
--    - narrator    : auteur / narrateur révélé par le fragment ;
--    - item_text   : contenu du texte (loretext) ;
--    - secret_text : texte caché (hiddentext) déverrouillé par le joueur.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS lore_items (
    id                BIGSERIAL PRIMARY KEY,
    wiki_page_id      BIGINT      NOT NULL
                      REFERENCES wiki_pages (page_id) ON DELETE CASCADE,
    series            TEXT        NOT NULL,
    item_name         TEXT        NOT NULL,           -- nom du fragment
    context           TEXT,                           -- quête liée, si connue
    planet            TEXT,                           -- lieu de découverte
    narrator          TEXT,                           -- auteur du texte
    item_text         TEXT        NOT NULL,
    secret_text       TEXT,
    audio             TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (wiki_page_id, item_name)
);

CREATE INDEX IF NOT EXISTS idx_lore_items_page ON lore_items (wiki_page_id);

-- ----------------------------------------------------------------------------
-- 8. Table warframes : annuaire / index des Warframes (base et Prime).
--    Une variante (frame_name, is_prime) est unique ; description reprend
--    l'accroche officielle FR du site.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS warframes (
    id                BIGSERIAL PRIMARY KEY,
    wiki_page_id      BIGINT      NOT NULL
                      REFERENCES wiki_pages (page_id) ON DELETE CASCADE,
    frame_name        TEXT        NOT NULL,           -- ex: 'Ash'
    is_prime          BOOLEAN     NOT NULL DEFAULT FALSE,
    description       TEXT,                           -- accroche officielle FR
    source_url        TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (frame_name, is_prime)
);

-- ----------------------------------------------------------------------------
-- 9. Table game_quests : index des quêtes du jeu.
--    - quest_type      : 'main' ou 'side' (inféré de la phrase d'intro) ;
--    - release_note    : formulation brute 'released in <...>';
--    - quest_context   : résumé (bloc de description de la page).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS game_quests (
    id                BIGSERIAL PRIMARY KEY,
    wiki_page_id      BIGINT      NOT NULL
                      REFERENCES wiki_pages (page_id) ON DELETE CASCADE,
    quest_name        TEXT        NOT NULL,
    quest_type        TEXT,
    release_note      TEXT,
    quest_context     TEXT,
    source_url        TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (wiki_page_id)
);

CREATE INDEX IF NOT EXISTS idx_quests_type ON game_quests (quest_type);

-- ----------------------------------------------------------------------------
-- 10. Table game_updates : notes de patch PC (mises à jour majeures et
--     correctifs).  version = forme en pointillés du slug de l'URL.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS game_updates (
    id                BIGSERIAL PRIMARY KEY,
    wiki_page_id      BIGINT      NOT NULL
                      REFERENCES wiki_pages (page_id) ON DELETE CASCADE,
    version           TEXT        NOT NULL,           -- ex: '39.0.0'
    update_title      TEXT,                           -- titre officiel
    update_type       TEXT,                           -- 'Mise à jour principale' / 'Correctif'
    release_date      TEXT,                           -- date lisible ('Jun 25, 2025')
    platform          TEXT        NOT NULL DEFAULT 'pc',
    summary           TEXT,                           -- premier paragraphe
    source_url        TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (wiki_page_id)
);

CREATE INDEX IF NOT EXISTS idx_updates_version ON game_updates (version);

-- ----------------------------------------------------------------------------
-- 11. Table game_announcements : actualités / annonces officielles du site
--     (futur contenu, événements, devstreams).  Une page /fr/news/ = une ligne.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS game_announcements (
    id                BIGSERIAL PRIMARY KEY,
    wiki_page_id      BIGINT      NOT NULL
                      REFERENCES wiki_pages (page_id) ON DELETE CASCADE,
    title             TEXT        NOT NULL,
    subtitle          TEXT,                           -- phrase d'accroche
    published_at      TEXT,                           -- 'Publié sur <horodatage>'
    summary           TEXT,                           -- premier paragraphe
    source_url        TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (wiki_page_id)
);

CREATE INDEX IF NOT EXISTS idx_announcements_published
    ON game_announcements (published_at);
