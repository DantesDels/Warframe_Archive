# v1 — Atlas: atelier de scraping multi-univers

**Statut : proposition de cible.** Ce document remplace `SCRAPER.md`
(snapshot de l'ancien scraper). La compatibilité avec les données produites
n'est pas exigée : format, schéma SQL et embeddings peuvent être régénérés.

---

## 1. Pourquoi on reprend à la source

L'ancien scraper encode **Warframe** partout : 4 sources codées en dur dans
`Scraper.__init__`, des buckets `Lore_*`, un canon status « canon/speculation »,
des cleaners Wikitext, des noms de fichiers `Lore_Quetes.json`. Aucune de ces
notions ne survit à un autre univers (un roman, un jeu concurrent, un domaine
juridique, une encyclopédie quelconque).

La nouvelle brique doit donc être un **atelier**, pas un pipeline figé :

- on crée un **dossier** (= un univers nommé) ;
- on **découvre** des sources en ligne pertinentes pour ce nom ;
- on **approuve / sélectionne / désélectionne / ajoute** ces sources ;
- on **lance** la récupération sur les sources retenues ;
- l'information est **triée** dès la récupération ;
- l'utilisateur choisit la ou les **sorties** (JSON, SQL, autres) ;
- tout est pilotable depuis une **UI**, pour un dossier, plusieurs, ou tous.

---

## 2. Vocabulaire

| Terme | Définition |
|---|---|
| **Dossier** (`Universe`) | Un univers nommé, isolé des autres. Porte ses sources, ses règles de tri et ses exécutions. Plusieurs dossiers coexistent. |
| **Source** | Une origine de données rattachée à un dossier. Trois kinds : `document`, `website`, `api`. |
| **Candidat** | Source proposée par la découverte, pas encore approuvée. Porte une preuve (d'où vient la proposition). |
| **Approbation** | Action utilisateur qui transforme un candidat en source active (ou le rejette). |
| **Exécution** (`Run`) | Une passe de récupération sur un dossier (ou un lot de dossiers), avec statut et statistiques. |
| **Tri** | Classification de chaque document récupéré : pertinence pour l'univers, type, thème, langue, doublons, qualité. |
| **Sink** | Destination de sortie. Plusieurs sinks peuvent être actifs en même temps. |

---

## 3. Exigences fonctionnelles

| # | Exigence |
|---|---|
| FR1 | Créer, renommer, supprimer un dossier ; en créer plusieurs. |
| FR2 | À partir du nom d'un dossier, examiner les sources disponibles en ligne en lien avec cet univers. |
| FR3 | Sur les sources trouvées : approuver, sélectionner, désélectionner, ajouter manuellement. |
| FR4 | Couvrir les documents, les sites web (scrape complet) et les URLs d'API. |
| FR5 | Trier les informations au moment de la récupération. |
| FR6 | Choisir la sortie : JSON, SQL, autres, ou plusieurs à la fois. |
| FR7 | Fournir une UI pour créer le dossier et importer / modifier ses sources. |
| FR8 | Lancer la mise à jour d'un dossier, de plusieurs dossiers sélectionnés, ou de tous. |
| FR9 | La source n'est pas nécessairement Warframe : aucun nom de jeu codé en dur. |

---

## 4. Architecture cible

**Racine de la refonte : `warframe_lore/v1/`.** Tout ce qui est créé dans la
branche `v1` vit sous ce dossier (et `tests/v1/`, `docs/v1/`). Le code
existant (`scraper/`, `storage/`, `engram/`, …) n'est **pas modifié** : la
nouvelle brique cohabite, elle ne casse rien. Les morceaux utiles de l'ancien
scraper (nettoyage Wikitext/HTML, découpage en chunks) pourront être réutilisés
plus tard comme étapes, sans dépendance structurelle.

```
warframe_lore/
  v1/
    universes/     # Universe, store JSON par dossier, service CRUD
    discovery/     # port DiscoveryProvider + providers (search, wiki…)
    sources/       # Source, SourceKind, registre, validation d'une URL
    fetch/         # fetchers: document, website (crawl complet), api
    sorting/       # règles de tri → SortedDocument + tags
    sinks/         # JsonSink, SqlSink, MarkdownSink, ... (port commun)
    runs/          # orchestration d'une exécution (1 ou N dossiers)
    cli/           # `python -m warframe_lore.v1.cli`
    ui/            # API + interface admin (FastAPI + statique léger)
```

Règles structurelles (AGENTS.md) : chaque dossier < 15 fichiers, chaque
fichier ≤ 100 LOC (hors blancs/commentaires/imports/données déclaratives),
tests hors périmètre de ces bornes.

### Dépendances

```
universes ──▶ sources ──▶ discovery
     │            │
     │            ▼
     │          fetch ──▶ sorting ──▶ sinks
     │                        │          │
     └──────────▶ runs ◀──────┘          │
                   │                     │
                   ▼                     ▼
                 cli                  ui (API)
```

`ui` et `cli` sont des **adapteurs** : ils appellent `runs` et `universes`,
jamais l'inverse. Aucun module de domaine n'importe FastAPI.

---

## 5. Modèle d'information

Stockage des dossiers : `data/v1/<slug>/universe.json` (KISS, lisible,
versionnable, indépendant de PostgreSQL). Le SQL n'est qu'un **sink** parmi
d'autres, pas le stockage de configuration.

```
Universe            Source                 RawDocument           SortedDocument
───────             ──────                 ───────────           ──────────────
id                  id                     id                    id
name (univers)      universe_id            source_id             raw_id
slug                kind (doc|site|api)    url_canonical         relevance: float
description         url / path             content_type          doc_type
status              status (candidate|     content (brut)        topics: list[str]
sources[]           approved|rejected|     checksum              language
sorting_rules[]     disabled)              fetched_at            quality: float
created_at          config (JSON)          http_status           is_duplicate
updated_at          discovered_by          metadata              tags
```

Invariant central : **un `RawDocument` garde toujours le contenu brut tel
qu'il a été récupéré.** Le tri et le nettoyage produisent des vues dérivées,
jamais une écrasure du brut. Cela rend le re-tri et la re-sortie possibles
sans réseau.

---

## 6. Pipeline d'une exécution

1. **Sélection** — un dossier, une sélection de dossiers, ou tous ; option de
   limiter aux sources actives.
2. **Découverte** (optionnelle) — propose des candidats pour le nom du dossier.
3. **Fetch** — par kind : document (fichier/URL), site (crawl BFS avec
   profondeur et limites), API (URL template + réponse JSON).
4. **Tri** — pertinence au nom du dossier, type de document, thèmes, langue,
   déduplication par checksum, score de qualité.
5. **Persistance du brut** — `RawDocument` immuable dans le dossier.
6. **Émission** — un ou plusieurs sinks, dans l'ordre choisi ; chaque sink
   indépendant, un échec n'empêche pas les autres.
7. **Rapport** — `Run` avec comptages (découverts / approuvés / récupérés /
   triés / émis par sink) et erreurs par source.

---

## 7. UI — écrans minimum

| Écran | Contenu |
|---|---|
| Dossiers | Liste, création (nom du univers), suppression, sélection multiple, « tout mettre à jour ». |
| Dossier | Description, sources actives, bouton « Examiner les sources en ligne ». |
| Découverte | Liste des candidats avec preuve et score ; approuver / rejeter / ajouter manuellement une URL. |
| Sources | Édition du kind, de l'URL/chemin, de la config (profondeur, selectors, headers), activer/désactiver. |
| Sorties | Choix des sinks actifs pour le dossier (JSON, SQL, autres). |
| Exécution | Lancement, progression, rapport par source et par sink. |

---

## 8. Découpage en tranches (rituel par tranche)

Chaque tranche = tests d'abord → implémentation → `graphify update` →
`ruff` + suite complète → commit sur `feat/v1-<nom>` → merge dans `v1`.

| # | Tranche | Preuve |
|---|---|---|
| S0 | Modèle `Universe` + store JSON + CRUD | créer 2 dossiers, les relister |
| S1 | `Source` + registre + validation d'URL | ajouter 3 kinds, source inconnue = erreur explicite |
| S2 | Découverte de candidats | examiner « Warframe » retourne des candidats probants |
| S3 | Fetch document + website + api | 3 sources → 3 `RawDocument` avec brut intact |
| S4 | Tri | chaque brut reçoit relevance/type/thèmes/langue/qualité |
| S5 | Sinks JSON + SQL + Markdown, multi-sinks | une exécution écrit dans 2 sinks simultanément |
| S6 | Runs multi-dossiers | mettre à jour 1, puis plusieurs, puis tous |
| S7 | UI admin | créer un dossier et approuver une source depuis l'UI |

---

## 9. Décisions à confirmer avant S0

Voir les questions posées dans la conversation : mécanisme de découverte,
technologie de l'UI, critères de tri, et liste des sinks « autres ».
Ces réponses conditionnent les ports à définir dans S0–S2.
