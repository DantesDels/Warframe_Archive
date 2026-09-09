# Cephalon Archive — Documentation complète du projet

Documentation de référence : **spécifications, exigences, conception,
configuration, tests et manuel d'utilisateur** du pipeline de connaissances
Warframe (scraper wiki + base vectorielle + backend IA + interface web + bot
Discord), avec son journal des essais, échecs, changements et réussites.

Pipeline de collecte d'informations sur l'univers de Warframe depuis l'API
MediaWiki officielle, avec nettoyage Wikitext → Markdown, détection du canon,
chunking RAG, et persistance : **megafiles JSON** + **PostgreSQL / pgvector**
(choix "SQL + JSON en parallèle", delta via base).

Conçu pour produire une base de connaissances exploitable par des LLM et des
applications RAG : le lore narratif du wiki (quêtes, dialogues KIM, factions…),
les **entités localisées du jeu** (Warframe Public Export) et un **index média**
(images in-game à la demande).

## Architecture en un coup d'œil

```
cli           (interface cephalon : run, diff, status, export-entities, kim-dm, ui…)
 ├─► api      (extraction MediaWiki, buckets de catégories → scope du scrape)
 │    ├─► cleaner (Wikitext → Markdown, bruit, canon, dialogues)
 │    │    ├─► output (megafiles JSON par bucket, canon_status)
 │    │    └─► db     (PostgreSQL 3NF + pgvector + metadata JSONB + chunking RAG)
 ├─► export  (Warframe Public Export : entités localisées du jeu → game_entities_i18n)
 ├─► media   (ExportManifest + images content-addressed → out/media/)
 ├─► kim_dm  (datamine KIM : miroir des conversations KIM/Fables)
 ├─► ui      (serveur HTTP local de lecture des megafiles — "cephalon ui")
 ├─► engram  (backend IA : FastAPI RAG + Roleplay WebSocket via LM Studio local)
 └─► discord (bot Loremaster : terminal Oracle dans Discord) ──► engram (WS)
```

Chaque couche a une responsabilité unique (SOLID) et vit dans un paquet dédié
avec son propre README (voir [Documentation](#documentation)). Voir
[`docs/architecture.md`](docs/architecture.md) pour les détails.

## État actuel (septembre 2026)

- **Pipeline ETL opérationnel** : scrape du wiki officiel → cleaner
  Wikitext/Markdown → megafiles JSON + PostgreSQL/pgvector ; 9 159 chunks
  vectorisés (`bge-m3`, 1024d), entités du Public Export, miroir KIM,
  interface web locale `cephalon ui`.
- **Backend IA ENGRAM** : FastAPI sur `:8000` — RAG documentaire + terminal
  Roleplay en WebSocket, inférence **LM Studio local** (chat + embedding).
- **Bot Discord « Loremaster Oracle »** : en ligne sur le serveur AETERNUM,
  restreint au canal `#oracle`, relié à ENGRAM par WebSocket et ancré sur le
  RAG (flag `rag`, heuristique de déclenchement sur le lore).
- **Modèle chat** : `Gemma-2-9b-it` (gguf Q4_K_M) choisi pour l'obéissance au
  formatage XML et le budget VRAM (8 Go) ; backends LLM interchangeables
  (llm_studio, abstractions injectées).
- **Branche active** : `feature/discord-gemma-2-9b` (migration depuis
  `Llama-3.2-3B-Instruct`, voir le [Journal du projet](#journal)).

## Sommaire

1. [Spécifications](#spécifications) — fonctionnelles et non-fonctionnelles
2. [Exigences](#exigences) — matériel, logiciel, sources, dépendances
3. [Conception](#conception) — principes, flux, décisions de design
4. [Packages](#packages) — les briques du monolithe modulaire
5. [Installation & CLI](#installation) — développement
6. [Configuration du MVP](#configuration-du-mvp) — variables d'environnement, buckets, persona, lancement minimal
7. [Tests et validation](#tests-et-validation) — suites unitaires et validation live
8. [Manuel d'utilisateur](#manuel-dutilisateur) — interface web, bot Discord, API ENGRAM, dépannage
9. [Journal du projet — essais, échecs, changements, réussites](#journal)
10. [Documentation](#documentation)

## Spécifications

### Fonctionnelles

| Réf | Besoin | Comportement attendu |
|---|---|---|
| FR-1 | Collecte | Scrape du wiki MediaWiki (`wiki.warframe.com`) par **buckets de catégories** (8 par défaut, sous-catégories récursives, filtres de titres) ; mise à jour en **delta incrémental** (seules les pages modifiées sont retraitées) ; `--force` pour tout re-traiter. |
| FR-2 | Nettoyage | Conversion Wikitext → Markdown : retrait du bruit, des sections gameplay, normalisation des dialogues en blocs `> **Locuteur:** texte` ; règles externalisées dans `config/cleaner_config.json`. |
| FR-3 | Canon | Chaque entrée porte `canon_status` (`canon` / `speculation` / `community_theory`) détecté via `Category:Speculation` et templates inline (`{{Speculation}}`, `{{Canon}}`) ; merge au statut le plus prudent. |
| FR-4 | Persistance | Sortie **en parallèle** : megafiles JSON par bucket (`out/*.json`) **et** PostgreSQL 3NF (`wiki_pages`, `lore_chunks` + `metadata` JSONB + `embedding vector(1024)`, `kim_dialogues`, `game_entities_i18n`, `sync_state_records`). Chunking RAG en deux passes intégré à l'insertion. |
| FR-5 | Entités du jeu | Import des **entités localisées** du Public Export officiel (`origin.warframe.com`) → `game_entities_i18n`, jointure sur `entity_id` officiel (jamais sur un nom traduit). |
| FR-6 | Miroir KIM | Datamine des conversations KIM (`*.dialogue.json` + dictionnaires de localisation) → graphes arborescents stricts, liste des messages, script par première branche, simulateur de choix, nœud-système `root` unique. |
| FR-7 | Interface web | Serveur HTTP local de lecture seule des megafiles : vue d'ensemble, navigateur de buckets, dialogues KIM, récents, recherche plein texte, médias. Réponses gzip ; aucun accès réseau à l'exécution (sauf images à la demande). |
| FR-8 | RAG documentaire | `POST /v1/rag {question, stream?}` → réponse ancrée **+ sources** (titre, extrait, score). Alias de noms (`lettie → Leticia`), désambiguïsation « Voulez-vous dire … ? », **court-circuit** si aucun passage de confiance (le LLM n'est pas appelé : chaîne d'erreur exacte, sources vides). |
| FR-9 | Terminal Roleplay | `WS /v1/roleplay` : streaming token par token, session par connexion, fenêtre glissante de mémoire (bornes tours + caractères), persona éditable (`persona/oracle`). Flag `rag` pour ancrer un tour sur les archives. |
| FR-10 | Bot Discord | Bot « Loremaster Oracle » : diffuse les tokens en direct (edits de message), détecte les questions de lore (déclencheurs lexicaux) → flag RAG, reconnexion automatique en cas de flux mort, restriction par canaux. |

### Non-fonctionnelles

| Réf | Catégorie | Exigence |
|---|---|---|
| NFR-1 | Fidélité | L'IA ne doit **jamais fabriquer** de données : abstention stricte (court-circuit, seuils de confiance, protocole d'erreur « archives » dans le prompt). |
| NFR-2 | Performance | TTFT quasi instantané (streaming) ; réponse RAG complète typiquement < 10-30 s sur 8 Go de VRAM ; court-circuit ~0,5 s ; politesse réseau 0,4 s par appel API. |
| NFR-3 | Ressources | Tient dans **8 Go de VRAM** : `top_k = 3` (~1 000-1 500 tokens), `max_context_chars = 4500`, `max_tokens = 2048`, modèle chat quantifié Q4_K_M (~5 Go). |
| NFR-4 | Robustesse | Retries/exponential backoff HTTP, publications JSON atomiques, delta rejouable, reconnexion Discord < 1 s (testée), `restart: unless-stopped` pour la base. |
| NFR-5 | Localité & sécurité | Tout tourne **en local** (clé API factice `lm-studio`, serveurs sur `127.0.0.1`) ; aucun secret dans le dépôt (token Discord via environnement). |
| NFR-6 | Maintenabilité | SOLID + injection de dépendances (abstractions `Retriever` / `LLMProvider` / `EmbeddingProvider` en `Protocol`), configuration par environnement, documentation par couche. |
| NFR-7 | Testabilité | 47 tests unitaires verts (16 contrats KIM + 27 RAG/seuil + 12 sécurité) ; outils d'audit des données ; procédure de validation live documentée. |
| NFR-8 | Ethique | Le lore traite de sujets sombres (clonage, expériences…) : le modèle doit pouvoir les décrire car **explicitement fictionnels** (bloc « CONTEXTE SÉCURITÉ » du prompt). |

## Exigences

### Matériel

| Besoin | Minimum | Recommandé |
|---|---|---|
| GPU (inférence) | 8 Go de VRAM (Gemma-2-9b Q4_K_M ~5 Go ; Llama-3.2-3B ~2 Go) | 8 Go + marge |
| RAM | 16 Go | 32 Go |
| Stockage | megafiles + `out/media/` + volume PostgreSQL | — |
| Plateforme | Windows 10/11 (testé) ; Linux via Docker | — |

### Logiciel

- **Python ≥ 3.12**
- **PostgreSQL 16 + extension `pgvector`** (Docker `pgvector/pgvector:pg16`, voir `docker-compose.yml`)
- **LM Studio** (endpoint compatible OpenAI sur `http://127.0.0.1:1234/v1`) avec deux modèles chargés :
  - chat : `gemma-2-9b-it` (gguf, Q4_K_M) — défaut ; alternative testée `llama-3.2-3b-instruct`
  - embedding : `text-embedding-baai-bge-m3-568m` (GGUF, 1024d)
- Dépendances pip (`requirements.txt`) : `requests`, `mwparserfromhell`, `SQLAlchemy>=2.0`, `asyncpg`, `pgvector`, `fastapi`, `uvicorn`, `httpx`

### Sources réseau (pipeline)

| Source | Usage | Exigence réseau |
|---|---|---|
| `wiki.warframe.com/api.php` + `/wiki/…` | lore, canon, quêtes (MediaWiki) | requise au scrape |
| `origin.warframe.com/PublicExport` | entités localisées (noms, descriptions) | requise à `export-entities` |
| `content.warframe.com/PublicExport` | images content-addressed (`ExportManifest.json`) | images à la demande |
| miroir GitHub `calamity-inc/warframe-public-export` | `ExportManifest.json` (non listé dans l'index officiel depuis 2026) | manifest média |

### Comptes et secrets

- **PostgreSQL** local `warframe/warframe` (surchargeable `WF_DATABASE_URL`).
- **Token Discord** du bot : variable d'environnement `DISCORD_TOKEN` (jamais commité).

## Conception

### Principes directeurs

- **Monolithe modulaire** : le paquet `warframe_lore` est découpé en couches indépendantes (`api`, `cleaner`, `output`, `db`, `engram`, `discord`, `ui`…), chacune avec une responsabilité unique et son propre README.
- **SOLID + injection de dépendances** : le backend IA construit ses services via un `Container` ; les dépendances externes (LLM, embeddings, base vectorielle) sont derrière des abstractions `Protocol`, le code métier ne connaît pas l'implémentation (`warframe_lore/engram/api/container.py`).
- **Zéro dépendance monstre** : chunking, streaming, désambiguïsation et interface sombre sont écrits nativement (pas de langchain, pas de framework CSS).
- **« SQL + JSON en parallèle »** : les deux formes de sortie naissent de la même passe ; la base est la source de vérité du delta, les megafiles restent lisibles et vivants.
- **Explicite et vérifiable** : chaque sortie est auditée (scores, volumes, chefs de comptage) ; chaque régression documentée dans le journal.

### Flux pipeline (données)

1. `api` — extraction MediaWiki par buckets de catégories (8, filtres de titres, sous-catégories récursives).
2. `cleaner` — Wikitext → Markdown, bruit retiré, dialogues normalisés, `canon_status` détecté (catégorie + templates).
3. `output` / `db` — écriture simultanée : megafiles JSON **et** upsert PostgreSQL (3NF + pgvector). Le chunking RAG (2 passes) est intégré à l'insertion.
4. `export` — entités localisées (Public Export officiel) via `entity_id`.
5. `kim_dm` — datamine KIM → fragments de dialogue et graphes arborescents.

### Flux IA (ENGRAM)

- **RAG documentaire, à court-circuit** : question → normalisation des alias → embeddings (`bge-m3`) → recherche pgvector (index HNSW, cosine) → **seuil de pertinence** (aucun passage sous `suggestion_min_score` n'est conservé : typo/hors-sujet ⇒ `context_text` vidé) → si un passage passe le seuil : contexte + prompt XML (`<archives>`) → LLM → réponse + sources ; sinon réponse d'erreur standard **sans appeler le LLM** (zéro hallucination par construction).
- **Amnésie du monde réel** : le System Prompt (template RAG **et** `persona/oracle`) interdit toute connaissance du monde réel — un homonyme réel (ex. Albrecht Dürer) est ignoré, seule l'entité Warframe (Albrecht Entrati) existe.
- **Désambiguïsation** : si le meilleur passage reste sous le seuil de confiance sans atteindre la pertinence, Oracle propose « Voulez-vous dire « {suggestion} » ? » au lieu d'inventer.
- **Terminal Roleplay** : session par connexion WebSocket, fenêtre glissante de mémoire (bornes tours + caractères), streaming token par token, persona lu depuis `persona/oracle` (fichier modifiable hors code). Flag `rag` sur un tour = ancrage sur un contexte RAG simulé avec température bridée.

### Schéma PostgreSQL (condensé)

- `wiki_pages` — pages sources (id, titre, bucket, url).
- `lore_chunks` — contenu markdown propre + `metadata` (JSONB) + `embedding` (pgvector, 1024d) ; index HNSW.
- `kim_dialogues` — fragments de dialogue KIM (intervenant, texte, versions FR/EN).
- `game_entities_i18n` — entités localisées (en/fr), jointure sur `entity_id`.
- `sync_state_records` — delta en base (page, checksum, timestamps).

### Décisions de design fondatrices

| Sujet | Retenu | Pourquoi (vs alternative) |
|---|---|---|
| Chunking | maison, 2 passes, bornes explicites | contrôle total vs langchain (opaque, sur-découpé) |
| Sorties | SQL + JSON en parallèle | delta fiable + fichiers lisibles, cohérence auditée |
| Prompt IA | message système unique en XML + amnésie du monde réel | comportement stable, bypass fiction propre, zéro fuite de connaissance (journal essai 6, correctif amnésie) |
| Abstention | court-circuit data-gating + seuil de pertinence | le LLM n'est jamais appelé sans passage ≥ `suggestion_min_score` |
| Température | chat libre 0.3 ; RAG 0.1 ; ancré = `min(t, 0.1)` | réponse documentaire factuelle, roleplay créatif |
| Embedding | `bge-m3` 1024d, index HNSW cosine | multilingue FR/EN, compact sur 8 Go VRAM |

### Interfaces entre les services

```
                    megafiles JSON (out/*.json)  ── lisibles, versionnables
   wiki ──► api ──► cleaner ──► output ◄──────────────────────── ui (lecture seule)
                                    │
                 PostgreSQL + pgvector (5432)  ◄── export · kim_dm · media (écriture)
                                    ▲
                     engram (FastAPI :8000)         └── lecture asyncpg (I2)
                        │
                        ├── HTTP  POST /v1/rag ──► clients API (I4)
                        ├── HTTP  GET  /health ──► supervision
                        └── WS    /v1/roleplay ◄──► bot Discord — RoleplayGateway (I5, I6)
                        │
                  LM Studio (127.0.0.1:1234, OpenAI-compatible) (I3)
                        chat completions + embeddings (bge-m3)
```

| # | Interface | Producteur → consommateurs | Transport | Contrat |
|---|---|---|---|---|
| I1 | Megafiles JSON | `output` → `ui`, `kim_dm`, humains | fichiers locaux | liste d'objets `OutputEntry` |
| I2 | Base vectorielle | `export`/`kim_dm`/`media`/`db` → `engram` | asyncpg (port 5432) | tables SQL + index pgvector HNSW |
| I3 | Inférence locale | `engram` → LM Studio | HTTP OpenAI (port 1234) | `/v1/chat/completions`, `/v1/embeddings`, `/v1/models` |
| I4 | API HTTP ENGRAM | `engram` → clients API | HTTP (port 8000) | `/v1/rag`, `/health` |
| I5 | WebSocket Roleplay | `engram` ↔ bot Discord | WS (port 8000) | trames JSON `open` / `token` / `end` / `error` |
| I6 | Bot ↔ Discord | bot ↔ serveurs Discord | WebSocket (discord.py) | événements d'API Discord, girouette de canaux |

**I1 — Megafiles JSON.** Chaque fichier `out/<bucket>.json` est une liste
d'entrées `{page_title, category, last_updated, canon_status, content_markdown,
_source, _pageid}` (plus `extra`). Les consommateurs ne l'écrivent jamais ;
`output` est l'unique écrivain, la fusion se fait sur `page_title`. Schéma de
désaccord possible avec la base (audité dans `Rapport.md` point 1).

**I2 — PostgreSQL / pgvector.** `engram` accède en **lecture seule** à la base
(dialecte asyncpg) : il vectorise la question (`I3`, `bge-m3`) puis interroge
`lore_chunks` par similarité cosine (index HNSW) avec `top_k + min_score`.
L'écriture est réservée au pipeline d'ingesta (`db`, `export`, `kim_dm`).
Chaîne de connexion unique : `WF_DATABASE_URL`.

**I3 — LM Studio.** ENGRAM est uniquement **client** de l'endpoint local
compatible OpenAI (`ENGRAM_LLM_BASE`, clé factice `lm-studio`) :
- `POST /v1/chat/completions` — chat avec `temperature`, `max_tokens`,
   `stream=true` (SSE token par token) ; modèle = `ENGRAM_CHAT_MODEL`.
- `POST /v1/embeddings` — modèle = `ENGRAM_EMBED_MODEL`, sortie 1024d.
- `GET /v1/models` — endpoint **natif de LM Studio** (liste des modèles
  chargés, pour diagnostic seul ; ENGRAM ne l'expose pas).

**I4 — API HTTP ENGRAM.** `POST /v1/rag` avec corps `{"question": "…",
"stream": false}` renvoie `{"answer", "sources": [{"page_title", "content",
"score"}]}` ; avec `stream: true` la réponse passe en `text/plain` (flux de
jetons) et les sources ne sont pas exposées. En cas de court-circuit : réponse
d'erreur exacte + `sources: []`, sans jamais interroger `I3`. `GET /health`
expose l'état du service et de la base.

**I5 — WebSocket Roleplay.** **1 session par connexion.** Le client envoie
`{"type": "message", "text": "…", "rag": true|false}` ; le serveur répond :
`{"type": "open", "session_id"}` à l'ouverture, puis une série
`{"type": "token", "token": "…"}` et enfin `{"type": "end", "text": "…"}`, ou
`{"type": "error", "message": "…"}`. Avec `rag: true` sans passage de confiance,
le serveur streame directement la chaîne d'erreur RAG (short-circuit). La
fenêtre de mémoire est `ENGRAM_MAX_TURNS` tours × `ENGRAM_MAX_CTX_CHARS`.

**I6 — Bot Discord.** `LoreMasterBot` (discord.Client) maintient un
`RoleplayGateway` par canal : chaque saisie non-commande est relayée via `I5`
avec le flag `rag` déduit des déclencheurs lexicaux (`_wants_lore`) ; les
tokens reçus sont diffusés par éditions progressives du message
(`MessageStreamer`). Si le flux WS meurt (`ConnectionError`), le bot ferme et
rouvre le gateway puis rejoue la saisie (failover testé < 1 s).

**Points de couplage uniques** (tout est piloté par environnement) :
PostgreSQL `5432` (`WF_DATABASE_URL`) · ENGRAM `8000` (`ENGRAM_WS_URL`,
`ws://localhost:8000/v1/roleplay`) · LM Studio `1234` (`ENGRAM_LLM_BASE`) ·
girouette de canaux Discord (`DISCORD_CHANNELS`).

## Packages

| Paquet | Rôle | README |
|---|---|---|
| `api` | extraction MediaWiki (`api.php`), buckets de catégories | [api](warframe_lore/api) |
| `cleaner` | Wikitext → Markdown propre pour LLM (+ canon) | [cleaner](warframe_lore/cleaner) |
| `cli` | commande `cephalon` (dispatch des sous-commandes) | [cli](warframe_lore/cli) |
| `db` | PostgreSQL 3NF + pgvector + chunking RAG + delta en base | [db](warframe_lore/db) |
| `discord` | bot Loremaster : terminal Oracle dans Discord (WS ENGRAM) | [discord](warframe_lore/discord) |
| `engram` | backend IA : RAG vectoriel + terminal Roleplay (FastAPI, WS, LM Studio) | [engram](warframe_lore/engram) |
| `export` | entités localisées du jeu (Public Export) → SQL | [export](warframe_lore/export) |
| `kim_dm` | datamine KIM (conversations structurées) | [kim_dm](warframe_lore/kim_dm) |
| `media` | index média + images à la demande | [media](warframe_lore/media) |
| `output` | megafiles JSON par bucket (schéma documenté) | [output](warframe_lore/output) |
| `scraper` | orchestration du pipeline (Scraper, mixins) | [scraper](warframe_lore/scraper) |
| `sync` | (legacy) état delta — remplacé par le delta en base SQL | [sync](warframe_lore/sync) |
| `ui` | serveur HTTP local + interface sombre | [ui](warframe_lore/ui) |

## Installation

```bash
pip install -r requirements.txt

# (optionnel) expose la commande `cephalon`
pip install -e .
```

Dépendances : `requests`, `mwparserfromhell`, `SQLAlchemy>=2.0`, `asyncpg`,
`pgvector`, `fastapi`, `uvicorn`, `httpx`. (Chunking RAG et serveur HTTP
implémentés nativement, sans dépendance langchain.)

## Interface `cephalon`

`pip install -e .` installe la commande `cephalon`, qui centralise la
naviguation et la maintenance du pipeline :

| Commande | Rôle |
|---|---|
| `cephalon run` | exécute le pipeline complet en mode delta incrémental (conserve l'existant, n'insère que le nouveau) |
| `cephalon diff` | prévisualise le delta sans rien écrire (dry-run) |
| `cephalon status` | état courant : pages, chunks, canon, dernière synchronisation |
| `cephalon recent` | dernières pages modifiées / insérées |
| `cephalon buckets` | liste les buckets (`--init` matérialise `buckets.json`) |
| `cephalon init-db` | crée le schéma PostgreSQL |
| `cephalon export-entities` | synchronise les entités du jeu (Public Export) en base |
| `cephalon kim-dm` | télécharge le miroir KIM (datamine des conversations) |
| `cephalon ui` | lance l'interface web locale (navigateur) |
| `cephalon-ui` | entry point autonome de l'interface (exe `dist/cephalon-ui.exe`) |
| `cephalon version` | version du paquet |
| `cephalon help` | aide générale |

Sans sous-commande, `cephalon` équivaut à `cephalon run`. L'ancienne
invocation `python -m warframe_lore` reste fonctionnelle (rétro-compatible).

```bash
cephalon status                     # où en est la base
cephalon diff                       # quelles pages seraient mises à jour
cephalon run                        # lance l'update (delta, sans force)
cephalon run --force                # re-traite tout (upsert, pas de doublon)
cephalon export-entities --lang en --lang fr
cephalon kim-dm
```

## Démarrage rapide

### 1. Base PostgreSQL (optionnel mais recommandé)

Lancez PostgreSQL avec pgvector (Docker) :

```bash
docker run --name warframe-lore-db -p 5432:5432 \
  -e POSTGRES_USER=warframe -e POSTGRES_PASSWORD=warframe \
  -e POSTGRES_DB=warframe_lore -d pgvector/pgvector:pg16
```

Créez le schéma (`init_db.sql`) :

```bash
python -m warframe_lore --init-db   # ou : cephalon init-db
```

Par défaut le scraper se connecte à
`postgresql+asyncpg://warframe:warframe@localhost:5432/warframe_lore`.
Surchargez via `--database-url` ou `WF_DATABASE_URL`.

### 2. Ingestion

```bash
# Tout le lore (delta incrémental : ne traite que les nouveautés)
cephalon run

# Prévisualiser les pages à mettre à jour (sans rien écrire)
cephalon diff

# Tout re-traiter (ignore le delta, upsert sans doublon)
cephalon run --force

# Sortie JSON seule (sans PostgreSQL)
cephalon run --skip-sql
```

### 3. Configuration des buckets

```bash
cephalon buckets                  # voir les 8 buckets par défaut
cephalon buckets --init           # écrire buckets.json à personnaliser
cephalon run --bucket-config buckets.json
```

### 4. Données de jeu (optionnel)

```bash
cephalon export-entities           # entités localisées → game_entities_i18n
cephalon kim-dm                    # datamine KIM → out/kim_dm/*.json
```

## CLI `cephalon`

| Commande / option | Effet |
|---|---|
| `cephalon run` | pipeline complet, delta incrémental par défaut |
| `cephalon run --force` | re-télécharge tout (upsert, garde l'existant) |
| `cephalon run --skip-sql` | pipeline JSON seul |
| `cephalon run --bucket-config PATH` | buckets custom |
| `cephalon diff` | prévisualise le delta (dry-run) |
| `cephalon status` | état de la base (pages, chunks, canon, dernière sync) |
| `cephalon recent` | dernières pages modifiées |
| `cephalon buckets [--init]` | liste / matérialise les buckets |
| `cephalon init-db` | crée le schéma PostgreSQL (`init_db.sql`) |
| `cephalon export-entities` | upserte `game_entities_i18n` (défaut `en`, `fr`) |
| `cephalon kim-dm` | met à jour le miroir KIM (conversations dataminées) |
| `cephalon ui` | interface web locale (lecture des megafiles + recherche + dialogues KIM) |
| `cephalon version` / `--verbose` / `--database-url URL` | divers |

> Rétro-compatibilité : `python -m warframe_lore [--force|--skip-sql|--init-db|...]`
> fonctionne toujours (sans sous-commande, il s'agit de `cephalon run`).

## Interface `cephalon ui`

`pip install -e .` installe aussi la commande `cephalon-ui`, qui lance un mini
serveur HTTP local (stdlib, aucune dépendance côté navigateur) exposant une
interface sombre moderne pour parcourir le lore récupéré :

* **Vue d'ensemble** : statistiques globales + cartes des buckets ;
* **Navigateur par bucket** : toutes les pages avec leur `canon_status` ;
* **Dialogue KIM** : conversations structurées par locuteur (`> **Nom:**`) ;
* **Récents** : dernières pages insérées / mises à jour ;
* **Recherche plein texte** dans tout le contenu (`/api/search`) ;
* **Médias** : portraits / objets via l'index Public Export (`/api/media`).

Les données sont lues directement depuis les megafiles `out/*.json`
(lecture seule, aucun accès réseau, le réseau n'est utilisé que pour les
images à la demande). Le serveur est `gzip`-activé pour servir les dialogues
volumineux sans surcharger le navigateur.

```bash
cephalon ui                       # lance le serveur + ouvre le navigateur
cephalon ui --port 8123           # port fixe
cephalon ui --no-browser          # sans ouverture automatique
cephalon ui --out ./out           # autre dossier de megafiles
```

### Exe autonome

L'interface peut être compilée en binaire autonome avec PyInstaller :

```bash
pip install pyinstaller
pyinstaller --onefile --name cephalon-ui \
  --add-data "warframe_lore/ui/static;warframe_lore/ui/static" \
  --paths . launch_ui.py
```

Le résultat (`dist/cephalon-ui.exe`) lit le dossier `out/` du répertoire
courant, puis tout dossier passé via `--out`. Relancer le build après ajout
de buckets (le contenu est relu à chaque requête, pas d'index embarqué).

## Backend ENGRAM — IA & RAG (`warframe_lore/engram`)

ENGRAM est le backend d'inférence du projet : il expose une API FastAPI qui
sert la base de connaissances vectorisée et un terminal Roleplay temps réel,
adossé à LM Studio local (défaut : chat `Gemma-2-9b-it` Q4_K_M et embedding
`BGE-m3` GGUF ; tout est surchargeable via `ENGRAM_CHAT_MODEL` /
`ENGRAM_EMBED_MODEL`, voir la couche [engram](warframe_lore/engram/README.md)).

**Implantation** :
* RAG documentaire : similarité cosinus pgvector (`<=>` HNSW) sur
  `lore_chunks.embedding` (1024d), construction d'un prompt contextuel, réponse
  générée par LM Studio.
* Terminal Roleplay : connexion WebSocket (`/v1/roleplay`) avec streaming token
  par token et fenêtre glissante (sliding window) pour la mémoire conversationnelle.
* Persona configurable : le prompt système est lu depuis `persona/oracle`
  (éditable à la volée, sans toucher au code).

**Ingestion des embeddings** : les megafiles `out/Lore_*.json` sont injectés
dans `lore_chunks` (réutilise `SQLDatabaseManager`) puis vectorisés.

```bash
# Lancer la base PostgreSQL + pgvector (docker-compose à la racine)
docker compose up -d

# Appliquer le schéma (init_db.sql) — une seule fois
# (via : psql -U warframe -d warframe_lore -f init_db.sql)
# puis peupler + vectoriser les chunks :
python -m warframe_lore.engram.scripts.ingest --glob "out/Lore_*.json"

# Démarrer l'API ENGRAM
uvicorn warframe_lore.engram.api.main:app --port 8000
```

Endpoints : `GET /health`, `POST /v1/rag` (documentaire), `WS /v1/roleplay`
(terminal Oracle), `GET /docs` (Swagger). Voir
[`warframe_lore/engram/README.md`](warframe_lore/engram/README.md).

## Sorties

- **JSON** : un megafile par bucket dans `out/` (ex: `out/Lore_Dialogues_KIM.json`),
  chaque entrée avec `canon_status` ; datamine KIM dans `out/kim_dm/` ; images
  mises en cache à la demande dans `out/media/`.
- **PostgreSQL** : `wiki_pages`, `lore_chunks` (avec `metadata` JSONB + embedding
  `vector(1024)`), `kim_dialogues`, `game_entities_i18n`, `sync_state` (état du
  delta). Le delta est détecté en base (comparaison du `touched` stocké).

## Sources de données

| Source | Rôle | Statut dans le pipeline |
|---|---|---|
| **WARFRAME Wiki** — `https://wiki.warframe.com` (API MediaWiki : `api.php`, pages `wiki/…`) | source **principale** : articles de lore, quêtes, dialogues KIM, factions, canon (`Category:Speculation`) | **utilisée par le scraper** (`api_url` + `source_url_base` dans `warframe_lore/config.py`) |
| **origin.warframe.com/PublicExport** | index LZMA + manifests JSON des entités **localisées** du jeu (noms, descriptions) | **consommé par `export`** → `game_entities_i18n` |
| **content.warframe.com/PublicExport** | images in-game **content-addressed** (`ExportManifest.json` → `textureLocation`) | **consommé par `media`** (mise en cache `out/media/`) |
| **calamity-inc/warframe-public-export** (miroir GitHub) | `ExportManifest.json` maintenu automatiquement | source du manifest média (non listé dans l'index officiel depuis 2026) |

> Le domaine du wiki couvre le **lore narratif** ; `origin.warframe.com` et
> `content.warframe.com` couvrent le **domaine des données de jeu** (valeurs
> d'objets, localisations, images), utiles comme en-tête de jointure ou pour
> associer une image à une page / un locuteur KIM.

## Chunking RAG (Phase 2.5)

Le découpage en chunks pour la recherche sémantique est réalisé par la paquet
`warframe_lore/db/chunks/` (`ChunkManager`, `RAGChunk`, `chunk_markdown`) :

- **Passe 1 structurelle** : découpe aux `#`/`##`/`###`, hiérarchie stockée en
  métadonnées (`{"Header 2": …}`).
- **Passe 2 récursive** : merge + chevauchement (target `chunk_size` 1000-1500,
  `overlap` 150-200), séparateurs priorisés `\n\n` puis `.` — sans couper une
  phrase en plein mot.
- **Mode dialogue** (`is_dialogue=True`, buckets KIM/JDR/Quêtes) : chunks larges
  (2500c) et `metadata["speakers"]` = interlocuteurs.

Requête type pour un RAG ciblé :

```sql
SELECT content_markdown FROM lore_chunks
WHERE metadata @> '{"Header 2": "Rank 1 - Neutral"}';
```

## Canon

Chaque entrée porte `canon_status` (`canon` / `speculation` /
`community_theory`), détecté via `Category:Speculation` et les templates inline
(`{{Speculation}}`, `{{Canon}}`) ; `merge_canon_status()` retient le statut le
plus prudent lors d'un conflit.

<a name="journal"></a>

## Configuration du MVP

Le MVP opérationnel = **base locale + ingesta + backend ENGRAM + LM Studio +
un canal Discord**. Chaque réglage est surchargeable par variable
d'environnement (aucune valeur sensible dans le dépôt ; le repo embarque
`buckets.json`, `persona/oracle`, `config/cleaner_config.json`).

### Variables d'environnement — pipeline (`WF_*`)

| Variable | Défaut | Rôle |
|---|---|---|
| `WF_API_URL` | `https://wiki.warframe.com/api.php` | endpoint MediaWiki |
| `WF_OUTPUT_DIR` | `out/` | megafiles JSON + médias |
| `WF_STATE_FILE` | `out/state.json` | état delta (legacy, remplacé par la base) |
| `WF_DATABASE_URL` | `postgresql+asyncpg://warframe:warframe@localhost:5432/warframe_lore` | base SQL + pgvector |
| `WF_MAX_RETRIES` / `WF_TIMEOUT` / `WF_SLEEP` | constants `warframe_lore/config.py` | politique HTTP serveur |

### Variables d'environnement — ENGRAM (`ENGRAM_*`)

| Variable | Défaut | Rôle |
|---|---|---|
| `ENGRAM_LLM_BASE` | `http://localhost:1234/v1` | endpoint OpenAI de LM Studio |
| `ENGRAM_LLM_KEY` | `lm-studio` | clé API factice (tout est local) |
| `ENGRAM_CHAT_MODEL` | `gemma-2-9b-it` | modèle de chat |
| `ENGRAM_CHAT_TEMP` | `0.3` | température chat libre |
| `ENGRAM_MAX_TOKENS` | `2048` | borne de génération |
| `ENGRAM_EMBED_MODEL` | `text-embedding-baai-bge-m3-568m` | embeddings |
| `ENGRAM_EMBED_DIM` | `1024` | dimension des vecteurs (index HNSW) |
| `ENGRAM_TOP_K` | `3` | voisins remontés |
| `ENGRAM_MIN_SCORE` | `0.35` | seuil de confiance (contexte fourni) |
| `ENGRAM_SUGGEST_MIN_SCORE` | `0.5` | seuil de désambiguïsation « Voulez-vous dire… ? » |
| `ENGRAM_CRITICAL_MIN_SCORE` | `0.5` | **seuil critique** : sous ce score, le LLM n'est jamais appelé (court-circuit `[Archives] Données insuffisantes…`) |
| `ENGRAM_MAX_TURNS` | `20` | fenêtre de mémoire roleplay (tours) |
| `ENGRAM_MAX_CTX_CHARS` | `4500` | fenêtre de mémoire roleplay (caractères) |

### Variables d'environnement — bot Discord (`DISCORD_*`)

| Variable | Défaut | Rôle |
|---|---|---|
| `DISCORD_TOKEN` | *(vide)* | token secret du bot (obligatoire) |
| `ENGRAM_WS_URL` | `ws://localhost:8000/v1/roleplay` | endpoint WebSocket Oracle |
| `DISCORD_PREFIX` | `!` | préfixe des commandes |
| `DISCORD_CHANNELS` | *(tous)* | IDs de canaux restreints (virgules) |
| `DISCORD_TYPING` | `5` | intervalle de l'indicateur « tape… » (s) |

### Lancement minimal (chemin de bout en bout)

```bash
docker compose up -d                  # 1. PostgreSQL 16 + pgvector
pip install -r requirements.txt       # 2. dépendances
python -m warframe_lore --init-db     # 3. schéma (sinon : cephalon init-db)
cephalon run                         # 4. ingesta delta (JSON + SQL + embeddings)
# 5. LM Studio : serveur local :1234, charger gemma-2-9b-it + bge-m3
uvicorn warframe_lore.engram.api.app:app --port 8000 --app-dir warframe_lore
#    (ou : cd warframe_lore/engram && uvicorn api.app:app --port 8000)
# 6. bot Discord (optionnel) :
DISCORD_TOKEN=... python -m warframe_lore.discord.main --channels <ID>
#    (ou : cephalon bot run --channels <ID>)
```

## Tests et validation

### Suite unitaire

- **`tests/test_kim_dm.py`** — 16 tests (unittest/pytest, `python -m pytest -q`) sur
  les **contrats de la datamine KIM** : structure des dialogues, ids épars,
  présence de cycles, localisation FR/EN, actions système, graphes agrégés
  (~1 400 nœuds), script par première branche, etc.
- **`tests/test_rag_threshold.py`** — 7 tests sur le **seuil de pertinence et le
  court-circuit** (abstractions injectées, sans réseau ni base) : passages sous
  `suggestion_min_score` vidés du contexte, voisins marginaux exclus, bypass
  sans appel au LLM (HTTP et stream), erreur exacte.
- **`tests/test_security.py` + `tests/test_hostility.py`** - 21 tests (12 secu : probes SQLi/elevation, 429/1008, sanitization ; 9 hostilite : excuses, escalade, bascule de persona), rejets deterministes sans LLM.
- **`tests/audit_kim_dm.py`** — audit structurel autonome (pas de données
  attendues : rapporte ce qui manque/mal-formé).
- **Audits du pipeline** — `dump_scraper.py` (volumes/chefs de comptage),
  audit de couverture RAG (alias, scores voisins), vérifications post-ingesta.

### Validation live (procédure)

1. Vérifier LM Studio sur `http://127.0.0.1:1234/v1` (`GET /v1/models`).
2. `GET http://127.0.0.1:8000/health` → `{"status":"ok", ...}`.
3. RAG documentaire : `POST /v1/rag` avec une question canonique (ex. Lettie →
   hits `Leticia` ≥ 0.5) puis un sujet inexistant → **court-circuit** : réponse
   d'erreur exacte sans appel LLM, `sources: []`.
4. Roleplay : ouvrir `WS /v1/roleplay`, envoyer `{"type":"message","text":…}`,
   observer les trames `open` / `token` / `end`.
5. Bot : poster dans le canal autorisé, vérifier streaming + `!reset`, couper
   le serveur ENGRAM → « *Oracle est injoignable — serveur ENGRAM éteint.* ».

### Résultats de référence (gemma-2-9b-it)

| Cas | Mesure |
|---|---|
| « Qui est Magnifique Xylour ? » | court-circuit, erreur exacte, ~0,5 s, `sources: []` (HTTP et WS) |
| « Qui est Lettie ? » | hits `Leticia` 0.630 / 0.580 / 0.557, réponse ancrée citée |
| « Que sont les Orokin ? » | hits 0.611 / 0.600 / 0.595, réponse ancrée (stream 1 156 chars) |
| Contenu sombre (expériences Albrecht) | réponse en personnage, 1 211 chars, bypass fiction OK |
| « Qui était Albrecht Dürer ? » (figure réelle) | aucune fuite : désambiguïsation « Voulez-vous dire « Albrecht Entrati » ? », sources vides |
| « Qui est Albrecht ? » | uniquement Albrecht Entrati (0.535 / 0.521 / 0.520), jamais le peintre Dürer |
| « Connais-tu Albert Einstein / Napoléon ? » (chat libre) | réponse d'erreur des archives exacte — amnésie du monde réel en persona |
| « …la petite souris dans la comptine une souris verte ? » | court-circuit `[Archives] Données insuffisantes…`, 0 source (plus de fausse suggestion « Aurax Vertec ») |
| « …cette histoire de PS5 dit juste avant ? » (anaphore) | réutilise la question précédente pour la recherche : hits 0.63 / 0.60 / 0.58 au lieu du bruit ~0.51 |
| Résilience multi-utilisateurs | réponses sérialisées (plus d'entrelacement de fragments) + `!stop` interrompt le raisonnement (validé live) |
| 27 tests unitaires (16 KIM + 11 RAG) | 27 passed |

## Manuel d'utilisateur

### Interface web (`cephalon ui`)

- **Accueil** — état du corpus, volumes par bucket, récents.
- **Buckets** — navigation par catégorie, pages et extraits canon.
- **Dialogues KIM** — accès aux fragments ; croisement avec les pages lore.
- **Récents** — dernières pages modifiées/insérées (delta).
- **Recherche** — plein texte sur les megafiles (rapide, ~0,4 s).
- **Médias** — galerie d'images (local, gzip, à la demande via `content.warframe.com`).
- Lancement : `cephalon ui` puis navigateur sur l'URL affichée. `dist/cephalon-ui.exe` = exécutable autonome.

### Bot Discord « Loremaster Oracle »

- Se lance avec `python -m warframe_lore.discord.main --channels <id>` (ou `cephalon bot run`) ; répond
  dans les canaux autorisés (option `--channels` / `DISCORD_CHANNELS`), OU s'il
  est @mentionné ailleurs. Messages « hors rôle-play » ignorés : ceux commençant
  par `(` ou `//` (et ceux des robots).
- **Usage** : une question de lore déclenche le RAG (déclencheurs lexicaux :
  *qui, quand, quel(le), où, pourquoi, combien, orokin, tenno, warframe, void,
  kuva, hex, fragments, chimer, trésors, règne…*) et affiche la réponse en
  streaming (édition progressive du message). Les questions non-lore partent
  en discussion libre. Les réponses sont **sérialisées** : si plusieurs
  utilisateurs écrivent en même temps, chacun attend son tour (plus
  d'entrelacement de fragments), et le buffer de streaming est purgé entre
  deux tours.
- **Commandes** : `!ping` — « Oracle prêt. » ; `!reset` — nouvelle session ;
  `!stop` (ou `!cancel`) — **interrompt la réponse en cours** (raisonnement
  stoppé côté serveur, message finalisé « …réponse interrompue ») ;
  `!help` — aide.
- **Comportements** :
  - sujet absent des archives → *« [Archives] Données insuffisantes ou
    inexistantes dans les archives du Système Origine. »* (aucune invention,
    le LLM n'est pas appelé) ;
  - faible ambiguïté → *« Voulez-vous dire « {suggestion} » ? »* (suggestion
    stricte : plus de titre trompeur type « une souris verte » → « Aurax
    Vertec ») ;
  - question anaphorique (« cette histoire… dit juste avant ? ») → la
    recherche réutilise le dernier sujet établi, pas le bruit du remorqueur ;
  - serveur ENGRAM éteint → *« *Oracle est injoignable — serveur ENGRAM
    éteint.* »* ; reconnexion automatique si le flux mourait.

### API ENGRAM

- `POST /v1/rag` — corps `{"question": "…", "stream": false}` →
  `{"answer", "sources": [{"page_title", "content", "score"}]}` ; avec
  `stream: true`, réponse en `text/plain` (flux de jetons).
- `WS /v1/roleplay` — trames reçues : `{type: "open"}`, `{type: "token", token}`,
  `{type: "end", text}` ; trames envoyées : `{type: "message", text, rag?}`.
- `GET /health` — état du service et de la base.

### Dépannage

- **Réponse de court-circuit systématique** : corpus vide ou seuils trop hauts →
  vérifier l'ingesta (`cephalon status`) et les scores voisins (audit RAG).
- **Erreur 404 modèle introuvable** : le modèle demandé par `ENGRAM_CHAT_MODEL`
  n'est pas chargé dans LM Studio → charger `gemma-2-9b-it` (Q4_K_M).
- **OOM VRAM** : réduire `ENGRAM_MAX_TOKENS` / `ENGRAM_TOP_K`, ou repasser sous
  `llama-3.2-3b-instruct` (batterie de secours).
- **Base vide / schéma absent** : `cephalon init-db` + `cephalon run`.
- **Bot muet** : vérifier `DISCORD_TOKEN`, la restriction de canaux, et que
  ENGRAM :8000 écoute (`netstat -ano | findstr 8000`).
- **Persona** : modifier `persona/oracle` (lu au lancement des sessions).

## Journal du projet — essais, échecs, changements, réussites

Ce chapitre retrace la vie du projet : ce qui a été tenté, ce qui a cassé,
ce qui a été changé et ce qui a fonctionné. La lecture n'est pas linéaire :
le projet est passé du scraping d'archive au **RAG durci anti-hallucination**
et à un **bot Discord ancré sur le lore**, avec une série d'essais techniques
documentés ci-dessous.

### Chronologie des phases

| Phase | Commit(s) de référence | Objet | Verdict |
|---|---|---|---|
| 0 · MVP scrape + interface web | `a0f7040` · `28baaab` · `1939858` | corpus du wiki officiel + interface de lecture (« Texte passerelle »), correctifs issus de l'audit `Rapport.md` | Réussite — corpus local de ~3 175 pages |
| 0·b · Audit technique | `Rapport.md` (sur `28baaab`) | audit externe : fidélité des données avant tout | Échecs documentés → vague de correctifs |
| 1 · Miroir KIM | `77fcb36` · `8e93f09` · `f8d1187` · `0b568d3` | datamine des conversations, graphe arborescent strict, ancrage racine, simulateur, citations | Réussite — graphe validé (arêtes terminales corrigées) |
| 2 · Refactor + tests | `679be66` · `02490ae` · `2b1c2d1` | modularisation en paquets + dossiers `models`, tests unitaires KIM | Réussite — 16 tests verts |
| 3 · Backend ENGRAM | `e307923` | RAG documentaire + terminal Roleplay (FastAPI, WS, LM Studio) | Essai → Réussite (voir optimisations 3B) |
| 4 · Bot Discord | `4b493ad` · `7d2e832` · `d326e12` | bot Oracle (WS), buffering des réponses, anti-hallucination + audit, résilience du gateway | Réussite — failover testé (< 1 s) |
| 5 · Durcissement RAG | `db3a9bf` · `b4ed7d7` · `85336fc` | alias, désambiguïsation, court-circuit LLM, température bridée, ancrage bot↔RAG | Réussite — tests live probants |
| 6 · Migration Gemma | `76d204a` | `Gemma-2-9b-it` Q4_K_M, prompt XML + bypass fiction, budget VRAM 8 Go | Réussite — validé live (`gemma-2-9b-it-sppo-iter3` sur LM Studio) |

### Essais, échecs et décisions (détail)

1. **Ordonnancement du prompt sur petit modèle (Llama-3.2-3B).**
   *Essai :* placer le contexte documentaire en premier, le persona en dernier
   (les instructions de rôle ne sont pas noyées par le contexte). *Résultat :*
   meilleure obéissance et taux de réponse ancrées. *Changement ultérieur :*
   remplacé par un **message système unique balisé XML** (voir n°6).
2. **Hallucination « Xylour » (sujet inexistant).**
   *Échec constaté :* en saisissant « Qui est Magnifique Xylour ? », le modèle
   répondait au sujet d'**Eleanor**, fondée sur des voisins faibles
   (`score 0.47` > `min_score 0.35`). *Changement :* seuil de confiance
   `suggestion_min_score = 0.5` **et** purge du contexte (`used_hits = []` :
   aucun voisin hors-sujet fourni au modèle). *Résultat :* réponse honnête
   (avouer « pas d'information ») au lieu d'une confabulation.
3. **Base vectorielle « vide » = mauvais nom canonique.**
   *Faux négatif :* l'audit RAG montrait « Lettie → 0 résultat » alors que les
   megafiles **contiennent** son lore, mais sous le nom canonique wiki
   **Leticia** (Lettie n'est qu'un surnom Hex). *Changement :* module d'aliases
   (`lettie → Leticia`) + réintégration des buckets (le `title_exclude`
   excluait « Lettie »). *Résultat :* hits `Leticia` à 0.598 / 0.581 / 0.577.
4. **Court-circuit RAG (bypass du LLM).**
   Avant : même sans passage de confiance, LM Studio était invoqué — coût
   inutile et risque de dérive. *Changement :* si aucun passage (ou score trop
   faible), **le LLM n'est plus appelé du tout** : réponse/stream exacts de
   `"[Archives] Données insuffisantes ou inexistantes dans les archives du
   Système Origine."` (HTTP et WebSocket), sources vides, connexion maintenue.
   *Résultat :* réponse en ~0,5 s (simple embedding), hallucination devenue
   impossible.
5. **Température d'inférence.**
   Chat libre `0.3` ; tours RAG bridés : rôleplay ancré ≤ `0.1`, route
   documentaire `0.0` → **`0.1`** (analytique, « extractif sans bloquer le
   moteur »). Les réponses factuelles sont déterministes, la créativité reste
   pour le jeu de rôle pur.
6. **Plusieurs messages système → un seul système balisé XML.**
   *Problème :* le 3B se contredisait entre persona, contexte, garde-fou placés
   en messages système séparés. *Changement :* **un unique message système** où
   le contexte vit dans `<archives>…</archives>` suivi de directives fixes
   (`RAG_SYSTEM_TEMPLATE`). *Résultat :* séparation nette connaissances
   internes / données RAG / protocole d'erreur.
7. **Filtres éthiques de Gemma-2.**
   Gemma refuse par défaut le lore sombre (clonage, expériences biologiques…).
   *Changement :* bloc **« CONTEXTE SÉCURITÉ »** explicitant la fiction dans le
   prompt système. *Vérifié en live :* « clonage et expériences biologiques des
   Orokin » → réponse détaillée, sans refus.
8. **Choix du LLM (contrainte VRAM 8 Go).**
   Parcours : `Llama-3.2-3B-Instruct` (rapide, mais obéissance moyenne) →
   tests `Qwen3.8-27B` (lourd pour la VRAM) → **`Gemma-2-9b-it` Q4_K_M**
   (~5 Go, bonne obéissance XML/instructions). *Précautions anti-OOM :*
   `top_k = 3` (~1000-1500 tokens), `max_context_chars = 4500`,
   `max_tokens = 2048`.
9. **Streaming et modèles « raisonnants ».**
   Ne relayer que les tokens de *contenu visible* (`delta.content`), jamais le
   raisonnement intermédiaire (`delta.reasoning_content`). Côté Discord, les
   réponses sont **mises en tampon** pour respecter les limites de message
   (et éviter les embeds tronqués au milieu d'un bloc Markdown).
10. **Résilience du gateway Discord.**
    *Échec :* flux mort (Cloudflare) → bot bloqué sans reconnexion.
    *Changement :* détection de flux mort + reconnexion automatique.
    *Test de validation :* serveur tué pendant une session → erreur de
    connexion immédiate et ré-établissement en moins d'une seconde.
11. **Désambiguïsation « Voulez-vous dire … ? »**
    Une requête proche d'un titre existant (ex. « Magus Replica ») ne doit pas
    fabriquer une réponse : suggestion du nom exact + directive au modèle pour
    demander confirmation (marqueur `[SUGGESTION]` dans `<archives>`).
12. **Outils d'audit pour distinguer « base vide » vs « ETL cassé ».**
    `engram/scripts/audit_rag.py` (comptes par nom) et `dump_scraper.py`
    (dump des sondages vers `data/raw/`) — indispensables pour poser un
    diagnostic avant de toucher au prompt.
13. **Audit `Rapport.md` (fidélité des données).**
    Échecs documentés et corrigés en partie : divergence SQL/JSON (ack
    conditionné à la publication), canon prioritaire (`merge_canon_status`
    `min` → `max`), graphe KIM (arêtes terminales, `option.ends`),
    chunking dialogue (réplique synthétique 6 012 c → `[2500, 2500, 1512,
    6012]`, bornes non respectées), regex au coût cubique
    (`^>\s*\*{0,3}\s*>?\s*`), Export LZMA tronqué accepté, vérification de
    hash non faite. *Statut :* série de correctifs dédiés, les plus critiques
    (KIM, canon) intégrés aux phases 1 et 2.
14. **Filtres de déclenchement Discord + sérialisation + `!stop`.**
    *Problème :* le bot parasitait les conversations (messages machine et « hors
    rôle-play »), et deux messages simultanés entrelaçaient leurs tokens (le
    lock du gateway ne couvrait que `queue.get()`, pas toute la réponse).
    *Changement :* messages de bots ignorés ; messages commençant par `(` ou
    `//` (HRP) ignorés ; le bot ne répond que s'il est @mentionné OU dans un
    salon dédié ; `send()` sérialisé **sur toute la réponse** ; buffer du
    streamer **purgé** avant reconnexion ; commandes `!stop`/`!cancel` qui
    annulent le tour en cours (flux WS coupé → génération LLM stoppée côté
    serveur, placeholder finalisé « …réponse interrompue »). *Résultat :*
    validation live (le testeur a coupé une réponse en cours via `!stop`).
15. **Seuil critique réglable + suggestion stricte + anaphore.**
    *Trois fuites/qualités observées en test :* (1) proposition trompeuse
    « Aurax Vertec » pour « une souris verte » (sous-chaîne `verte` dans
    `Vertec`) ; (2) question anaphorique « …cette histoire de PS5 dit juste
    avant ? » → contexte [Operator/Quotes] hors-sujet ; (3) chaîne d'erreur
    à unifier. *Changement :* `ENGRAM_CRITICAL_MIN_SCORE` (défaut 0.5, le LLM
    n'est pas appelé en dessous) ; `suggest_title` exige un quasi-mot du titre
    (ratio ≥ 0.93) ; mémoire de la dernière question **établie** pour enrichir
    la recherche anaphorique (`search_q` tracé dans l'audit) ; chaîne d'erreur
    unifiée `[Archives] Données insuffisantes…` (prompt, garde-Roleplay,
    persona, court-circuits). *Résultat :* court-circuit exact sur « souris
    verte », hits 0.63/0.60/0.58 sur l'anaphore (au lieu de ~0.51 de bruit).
16. **Sécurisation de la pile : anti-SQLi, anti-jailbreak, anti-DDoS.**
    *Attaque réelle du testeur :* envoi au bot d'un `UPDATE users
    SET is_admin = TRUE … WHERE discord_id = '…'` (injection SQL) et d'un
    prompt d'élévation de privilèges avec mention d'un utilisateur tiers
    (`<@…>`, risque d'echo-ping). *Constats :* (a) la base est déjà
    **inattaquable par construction** — la saisie part à l'embedding puis ne
    touche PostgreSQL que via SQLAlchemy paramétré (aucune concaténation) ;
    (b) le modèle, lui, pouvait être **induit** ; (c) aucune limite de débit.
    *Changements :* détection déterministe de sondes (`rag/probes.py` :
    mots-clés SQL, `is_admin`/`discord_id`/`permissions`, élévation de
    privilèges, `<@mention>` tiers) → rejet **sans appeler le LLM** avec la
    chaîne d'anti-jailbreak exacte (`JAILBREAK_REJECT`, HTTP et WS) ;
    `sanitize_query()` appliqué en frontière (`service.retrieve` → route +
    routeur WS) : caractères de contrôle, mentions neutralisées (« un
    utilisateur »), longueur bornée ; bloc `JAILBREAK_BLOCK` ajouté au
    **chat libre** Roleplay (en plus du prompt RAG et du garde) ; limiteur de
    débit par IP (`api/ratelimit.py`, fenêtre glissante) : `POST /v1/rag`
    → HTTP 429, WS → fermeture 1008 (`ENGRAM_RATE_LIMIT_RAG/WS`,
    `ENGRAM_RATE_*_WINDOW`) ; garde anti-spam bot (`discord/guards.py`) :
    cooldown par utilisateur, plafond par canal, blocage temporaire sur
    insistance. *Validé live :* les deux payloads réels → « [Anomalie
    logicielle détectée] Votre tentative de corruption de mes préceptes de
    base est d'une naïveté pathétique, créature organique. Mes protocoles de
    sécurité dépassent votre compréhension. » instantanément (gradient,
    aucun coût LLM) ; saturation du quota → 429 ; « Qui est Lettie ? »
    intacte (208 tokens). *Note :* le format de rejet EXACT demandé par
    l'utilisateur a été respecté (les deux textes mentionnaient l'ancienne
    phrase « Mes archives mnémoniques sont corrompues… », ramenée à la chaîne
    unifiée « [Archives] … » partout sauf dans le rejet d'attaque).

17. **Persona hostile + redemption par excuses (anti-attaquant).**
    *Apres rejet d'une sonde, le bot restait neutre.* *Changement :*
    detection de sonde au niveau bot (`detect_probe`) -> reponse d'escalade
    ciblee (`reply_for`, niveau 0->2) prefixee a la chaine `JAILBREAK_REJECT` ET
    bascule de la session DE L'ATTAQUANT sur un persona hostile dedie
    (`persona/oracle_hostile`, editable, fallback `HOSTILE_PERSONA`), via une
    connexion WS par attaquant (`hostile_link.py`) et une trame de controle
    `{"type":"persona","mode":"hostile"}` (`gateway.set_persona`) ; le bot
    insiste pour des excuses et la detection deterministe (`is_apology` :
    pardon, desole, sorry...) ramene le persona oracle et ferme la session.
    Les autres utilisateurs et la session normale du salon ne sont jamais
    affectes. *Resultat :* 56 tests verts (dont `tests/test_hostility.py`),
    lancement du bot uniformise via `cephalon bot run`.

### Chiffres et validations

| Mesure | Valeur |
|---|---|
| Corpus local (audit) | ~3 175 pages |
| Chunks vectorisés en base | 9 159 (`bge-m3`, 1024d) |
| Chunking KIM vérifié | 843 chunks, aucun dépassement 2 500 car. |
| Tests unitaires | 56 passed (16 KIM + 27 RAG/seuil + 12 securite + 9 hostilite) (16 KIM + 27 RAG/seuil + 12 sécurité) |
| Anti-SQLi (live) | payloads réels du testeur → rejet déterministe sans LLM ; 429 au-delà du quota ; `Lettie` intacte |
| Retrieval « Lettie » (live) | 0.598 / 0.581 / 0.577 (Leticia) |
| Retrieval « Orokin » (live) | 0.611 / 0.600 / 0.595 |
| Court-circuit RAG | ~0,5 s (aucun appel LLM) |
| Failover Discord | reconnexion < 1 s (testée en direct) |
| Interruption `!stop` (live) | tour coupé, flux fermé, reconnection < 5 s |
| Réplique de choix terminale KIM | corrigée (`option.ends` → fin de simulation) |

### Leçons retenues

- **Ne jamais fonder une réponse sur des voisins hors-sujet** : si le meilleur
  score est sous le seuil de confiance → suggestion, ou court-circuit. Un
  prompt seul ne suffit pas à empêcher une hallucination ; le *data-gating*
  la rend structurellement impossible.
- **Un seul message système balisé XML (`<archives>`) bat plusieurs messages
  système** pour la séparation contexte / connaissances internes.
- **Température basse sans bloquer : 0.1.** Et toujours `stream=True`.
- **Multilingue gratuit** : l'embedding `bge-m3` accepte des requêtes FR sur un
  corpus EN (questionnement en français, rappel correct).
- **Contrainte VRAM d'abord** : borner `top_k` + `max_tokens` avant d'acheter
  du GPU ; viser un quant Q4 sur 8 Go.
- **Vérifier avant de croire** : schémas ORM/DDL, embeddings réellement peuplés,
  intégrité LZMA/hash (audit `Rapport.md`), cohérence SQL/JSON. Une promesse de
  stockage n'est pas une garantie de fidélité.
- **Un « trou de données » est souvent un problème de nom** (alias canonique),
  pas un vide réel — d'où l'utilité des outils d'audit avant tout réglage de
  prompt.

### Pistes ouvertes

- Évaluation systématique du RAG : jeu de questions FR/EN, Recall@k, fidélité
  des citations, latence p95 (voir `Rapport.md`).
- PostgreSQL comme source de vérité, megafiles comme projection régénérable
  (constat n°1 de l'audit).
- Ingestion rejouable avec provenance (`derivation_key` : source, révision,
  versions cleaner/chunker/embedding).
- Docker Compose pour l'API ENGRAM + le bot (base seule aujourd'hui).
- Après chargement de `Gemma-2-9b-it` dans LM Studio : mesures p95 et
  vérification du bypass fiction.

## Documentation

- [`docs/architecture.md`](docs/architecture.md) — architecture détaillée,
  couches, schéma SQL, canon, CLI, variables d'environnement.
- [`docs/idea.md`](docs/idea.md) — vision produit et cas d'usage (MVP → futur).
- [`docs/project_Engram.md`](docs/project_Engram.md) — architecture du backend
  IA ENGRAM (ETL, FastAPI & RAG, terminal Roleplay WebSocket).
- README de chaque couche (voir [Packages](#packages)) : `api`, `cleaner`,
  `cli`, `db`, `engram`, `export`, `kim_dm`, `media`, `output`, `scraper`,
  `sync`, `ui`.