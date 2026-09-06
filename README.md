# Cephalon Archive — Warframe Lore Scraper

Pipeline de collecte d'informations sur l'univers de Warframe depuis l'API
MediaWiki officielle, avec nettoyage Wikitext → Markdown, détection du canon,
chunking RAG, et double persistance : **megafiles JSON** + **PostgreSQL /
pgvector** (choix "SQL + JSON en parallèle", delta via base).

Conçu pour produire une base de connaissances exploitable par des LLM et des
applications RAG.

## Architecture en un coup d'œil

```
api   (extraction MediaWiki, buckets de catégories)
 ├─► cleaner (Wikitext → Markdown, bruit, canon, dialogues)
 │    ├─► output (megafiles JSON par bucket, canon_status)
 │    └─► db     (PostgreSQL 3NF + pgvector + metadata JSONB + chunking RAG)
 └─► sync  (delta incrémentiel)
```

Chaque couche a une responsabilité unique (SOLID). Voir
[`docs/architecture.md`](docs/architecture.md) pour les détails.

## Installation

```bash
pip install -r requirements.txt

# (optionnel) expose la commande `cephalon`
pip install -e .
```

Dépendances : `requests`, `mwparserfromhell`, `SQLAlchemy>=2.0`, `asyncpg`,
`pgvector`. (Le chunking RAG est implémenté nativement, sans dépendance
langchain.)

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
python -m warframe_lore --init-db
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
* **Recherche plein texte** dans tout le contenu (`/api/search`).

Les données sont lues directement depuis les megafiles `out/*.json`
(lecture seule, aucun accès réseau). Le serveur est `gzip`-activé pour servir
les dialogues volumineux sans surcharger le navigateur.

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

## Sorties

- **JSON** : un megafile par bucket dans `out/` (ex: `out/Lore_Dialogues_KIM.json`),
  chaque entrée avec `canon_status`.
- **PostgreSQL** : `wiki_pages`, `lore_chunks` (avec `metadata` JSONB + embedding
  `vector(384)`), `kim_dialogues`, `sync_state_records`. Le delta est détecté en
  base (colonnes `last_updated`).

## Sources de données

| Source | Rôle | Statut dans le pipeline |
|---|---|---|
| **WARFRAME Wiki** — `https://wiki.warframe.com` (API MediaWiki : `api.php`, pages `wiki/…`) | source **principale** : articles de lore, quêtes, dialogues KIM, factions, canon (`Category:Speculation`) | **utilisée par le scraper** aujourd'hui (`api_url` + `source_url_base` dans `warframe_lore/config.py`) |
| **browse.wf** — `https://browse.wf/` (open-source liegen axe de calamity-inc) | données de jeu brutes issues de `warframe-public-export-plus` (exports `Export*`, images in-game, localisations, `kim-convo-locator`) | source **complémentaire identifiée** pour l'enrichissement (stats d'objets, images assets, localisations) — pas encore consommée par le pipeline |

> Le domaine du wiki couvre le **lore narratif** (pages lues, nettoyées et
> stockées par les buckets) ; `browse.wf` couvre le **domaine des données de
> jeu** (valeurs numériques des armes, warframes, mods…), utile comme en-tête
> de jointure ou pour associer une image à une page.

## Chunking RAG (Phase 2.5)

Le découpage en chunks pour la recherche sémantique est réalisé par
`warframe_lore/db/chunker.py` (`ChunkManager`) :

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
`community_theory`), détecté via `Category:Speculation` et les marqueurs inline
`[NON-CANON / SPECULATION JOUEUR]` ; `merge_canon_status()` retient le statut le
plus prudent lors d'un conflit.

## Documentation

- [`docs/architecture.md`](docs/architecture.md) — architecture détaillée,
  couches, schéma SQL, canon, CLI, variables d'environnement.
- [`docs/idea.md`](docs/idea.md) — vision produit et cas d'usage (MVP → futur).
- README de chaque couche : [`warframe_lore/api`](warframe_lore/api),
  [`warframe_lore/cleaner`](warframe_lore/cleaner),
  [`warframe_lore/output`](warframe_lore/output),
  [`warframe_lore/sync`](warframe_lore/sync),
  [`warframe_lore/db`](warframe_lore/db).