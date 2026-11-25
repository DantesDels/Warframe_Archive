# v1 — Pipeline aval : GraphEngine + ObsidianSynthesizer

Deux étages aval **indépendants** du Scraper v1, ajoutés sans modifier son
cœur. Toute la structure cible est pilotée par un fichier `blueprint.yaml`
(aucune référence à un univers spécifique dans le code métier).

→ Guide détaillé du fonctionnement : [`AVAL_ARCHITECTURE.md`](AVAL_ARCHITECTURE.md).

```
Scraper v1 (existant)
  └─ exports/<univers>/run-*/            chunks.jsonl · documents.jsonl · manifest.json (1.1)
       │
       ▼
Étage 2 — warframe_lore/v1/graph_engine/
  Map      extraction LLM par lots via LlmPort réutilisé (LM Studio ou API)
  Reduce   résolution d'alias, fusion, remap global des relations
  Analyse  centralité (pivots), communautés (modularité), ponts entre arcs
  Store    GraphStorePort → JsonGraphStore (graph.json, cache Map, manifeste)
       │
       ▼
Étage 3 — warframe_lore/v1/synthesizer/
  Micro    1 note par entité (faits sourcés, tableau relationnel, Mermaid 1 saut)
  Méso     1 note par communauté/arc (membres, interactions, enjeux)
  Macro    00_Vue_Globale.md (équilibres, chronologie, ponts) + canvas global
  Vault    VaultExporterPort → ObsidianVaultExporter (dossiers blueprint,
           _Index.md, 00_Index.md, auto-linking [[Nom|Alias]], callouts cite)
  Sync     .synthesizer/manifest.json (content_hash) · locked: true jamais écrasé
```

## Contrats

- **Modèles** (`graph_engine/models.py`) : `Entity` (id, name, entity_type,
  aliases, attributes, facts), `Fact` (statement, source_id, arc_or_context),
  `Relation` (source_id_entity, target_id_entity, relation_type,
  arc_or_context, dynamic_or_evolution, source_ids). Le `source_id` est
  toujours le `chunk_id` du Scraper v1 (`doc-…::index`).
- **Blueprint** (`v1/blueprint.py`, exemple : `v1/configs/blueprint.example.yaml`) :
  types d'entités (label + dossier numéroté), types de relations (label),
  sections par niveau (rôles → titres), styles (Mermaid, canvas), layout du
  vault. L'extraction rejette tout type non déclaré. Le schéma est compatible
  avec le parseur YAML stdlib existant (`parse_config_text`), sans dépendance.
- **Incrémentalité étage 2** : manifeste `chunk_id → SHA-256(texte)` ; un lot
  n'est ré-extrait que si un de ses chunks a changé ; les résultats Map sont
  persistés (reprise sans rappel LLM) ; un échec LLM n'est pas acquitté
  (retry au run suivant).
- **Incrémentalité étage 3** : manifeste `.synthesizer/manifest.json` par
  note (`content_hash` du payload d'entrée) ; seules les notes dont les
  sources ont changé sont régénérées ; `locked: true` dans le frontmatter
  d'une note existante interdit toute écrasure.

## Lancement

```
python -m warframe_lore.v1.aval_cli \
  --export-dir <dossier run-*> --blueprint <blueprint.yaml> \
  --store-dir <dossier graphe> --vault-dir <vault Obsidian> \
  [--endpoint http://127.0.0.1:1234/v1 --model <nom>]
```

Sans `--model`, l'adapter LLM budget-aware ne fait aucun appel (graphe vide) :
brancher un modèle local (LM Studio) ou une API compatible OpenAI.

## Tests

`tests/v1/test_graph_engine_contract.py` et
`tests/v1/test_synthesizer_contract.py` (fakes partagés :
`tests/v1/aval_fakes.py`, mini-univers fictif générique « Chronicles of
Aurelia ») : extraction/fusion d'alias, relations typées/temporalisées,
communautés/ponts, reprise incrémentale, auto-linking, Mermaid, canvas JSON,
sync incrémentale et protection `locked`.