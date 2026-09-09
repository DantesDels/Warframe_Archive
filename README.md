# Cephalon Archive — Warframe Lore Scraper

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
| 6 · Migration Gemma | `76d204a` | `Gemma-2-9b-it` Q4_K_M, prompt XML + bypass fiction, budget VRAM 8 Go | En cours — modèle à charger dans LM Studio |

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
   `"[Erreur] Mes archives mnémoniques sont corrompues ou incomplètes
   concernant ce sujet."` (HTTP et WebSocket), sources vides, connexion
   maintenue. *Résultat :* réponse en ~0,5 s (simple embedding), hallucination
   devenue impossible.
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

### Chiffres et validations

| Mesure | Valeur |
|---|---|
| Corpus local (audit) | ~3 175 pages |
| Chunks vectorisés en base | 9 159 (`bge-m3`, 1024d) |
| Chunking KIM vérifié | 843 chunks, aucun dépassement 2 500 car. |
| Tests unitaires | 16 passed |
| Retrieval « Lettie » (live) | 0.598 / 0.581 / 0.577 (Leticia) |
| Retrieval « Orokin » (live) | 0.611 / 0.600 / 0.595 |
| Court-circuit RAG | ~0,5 s (aucun appel LLM) |
| Failover Discord | reconnexion < 1 s (testée en direct) |
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