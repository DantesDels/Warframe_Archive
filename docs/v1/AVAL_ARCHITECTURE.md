# v1 — Guide détaillé : `graph_engine` et `synthesizer`

> Vue d'ensemble rapide : [`AVAL.md`](AVAL.md). Ce guide explique **comment**
> les deux étages aval construisent et publient le graphe, quels fichiers ils
> lisent/écrivent, et pourquoi leurs choix garantissent reprise, traçabilité
> et indépendance vis-à-vis de l'univers exploré.

---

## 1. Principes directeurs

| Principe | Conséquence concrète |
|---|---|
| Découplage | Le Scraper v1 n'est ni importé ni modifié par les étages aval. Ils consomment uniquement les **artefacts publiés** d'un dossier `run-*`. |
| Universalité | Aucun nom, type ou chemin lié à un univers n'est codé en dur dans `graph_engine/`, `synthesizer/` ou `blueprint.py`. Tout vient du `blueprint.yaml`. |
| Ports | `LlmPort` et `GraphStorePort` (étage 2), `VaultExporterPort` (étage 3) sont des `Protocol` : les adapters sont remplaçables en tests comme en production. |
| Déterminisme | Identifiants `stable_id`, tri explicite des sorties, hachages stables : deux exécutions avec les mêmes entrées produisent les mêmes fichiers. |
| Zéro dépendance graphe | Pas de `networkx`, pas de PyYAML obligatoire : analyse en Python pur, blueprint lu via le parseur YAML/JSON stdlib du dépôt. |
| Traçabilité | Chaque fait et chaque relation porte un `source_id` = `chunk_id` du Scraper ; les extraits bruts sont conservés pour les citations. |

L'étage 3 est **purement dérivationnel** : il n'appelle jamais le LLM. Il ne fait que renderer le `KnowledgeGraph` produit par l'étage 2.

---

## 2. Chaîne complète

```text
exports/<univers>/run-*/
  ├─ chunks.jsonl       → SourceChunk(chunk_id, text, url, section, …) + SHA-256(texte)
  ├─ documents.jsonl    → document_id → titre (pour les citations)
  └─ manifest.json      → contrôle du digest de chunks.jsonl (avertissement seulement)
         │
         ▼
GraphEngine.run(export_dir)                         [warframe_lore/v1/graph_engine/]
  Map      lots de N chunks → LlmPort → ExtractedBatch validé
  Cache    extracted/<sha1(chunk_id)[:16]>.json + manifest.json (chunk_id → hash)
  Reduce   cluster d'alias → fusion → remap global des relations → KnowledgeGraph
  Analyse  centralité, communautés, ponts → GraphAnalysis
  Store    graph.json (via GraphStorePort / JsonGraphStore)
         │  KnowledgeGraph (en mémoire, identique à graph.json)
         ▼
ObsidianSynthesizer.synthesize(graph)               [warframe_lore/v1/synthesizer/]
  Plan     NotePlan[] : micro, méso, macro, canvas, index
  Sync     SHA-256(payload) comparé à .synthesizer/manifest.json ; locked: true = jamais écrit
  Vault    VaultExporterPort / ObsidianVaultExporter → fichiers .md et .canvas
```

Le point de passage entre les deux étages est le `KnowledgeGraph`, pas le disque : la CLI conserve l'objet retourné par `GraphEngine.run()` et le passe directement au synthesizer.

---

## 3. Contrat d'entrée : l'export Scraper v1

`graph_engine/documents.py` est la seule porte d'entrée vers le Scraper.

| Fichier | Utilisation | Détail |
|---|---|---|
| `chunks.jsonl` | Source de vérité | Chaque ligne donne `chunk_id`, `text`, `source_id`, `url`, `section`, `version`. Ligne mal formée → avertissement et ignore ; chunk sans `chunk_id` ou texte vide → ignore. |
| `documents.jsonl` | Titres | `id` → `title` (repli : l'`id` lui-même). Sert d'étiquette aux callouts de sources. |
| `manifest.json` | Contrôle d'intégrité | Le `sha256` de `chunks.jsonl` est comparé à l'entrée `files[name=chunks.jsonl]` ; un écart loggue un avertissement mais **ne bloque pas** le run. |

`SourceChunk.content_hash()` est le SHA-256 du **texte seul** : c'est la clé d'incrémentalité. `document_id` est déduit de `chunk_id.split("::")[0]`, donc le format de `chunk_id` produits par le Scraper (`doc-…::index`) sert de provenance stable.

Le graphe conserve tous les chunks dans `graph.sources` sous forme de `SourceExcerpt(text, url, document_title, source_id)`, même ceux qui n'ont pas produit d'entité.

---

## 4. Le blueprint : unique source de structure

`v1/blueprint.py` charge un YAML (ou JSON) avec `parse_config_text` (parseur stdlib de `json_collection.config_parser`, réexporté par `config_loader`) puis valide et typifie le résultat dans `Blueprint`.

```yaml
name: "Generic narrative blueprint"

entity_types:                 # obligatoire, non vide
  character:
    label: "Personnages"
    folder: "01_Personnages"
  event:
    label: "Événements"
    folder: "04_Evenements"

relation_types:               # obligatoire, non vide
  ALLIED_WITH:
    label: "allié de"
  OPPOSES:
    label: "opposé à"

sections:                     # obligatoire : rôles → titres affichés
  micro:
    identity: "Identité"
    facts: "Faits établis"
    relations: "Relations"
    sources: "Sources"
  meso:
    members: "Membres"
    interactions: "Interactions internes"
    stakes: "Enjeux"
    sources: "Sources"
  macro:
    overview: "Vue d’ensemble"
    balance: "Grands équilibres"
    timeline: "Chronologie"
    bridges: "Ponts"

styles:                       # obligatoire (mapping), clés optionnelles
  mermaid_direction: "LR"
  canvas_node_width: 260
  canvas_node_height: 120
  canvas_columns: 4
  timeline_entity_type: "event"

vault:                        # arcs_folder, macro_note, root_index obligatoires
  arcs_folder: "06_Arcs"
  macro_note: "00_Vue_Globale.md"
  macro_title: "Vue globale"
  root_index: "00_Index.md"
```

Exemple complet et commenté : `warframe_lore/v1/configs/blueprint.example.yaml`.
Utilisez des **mappings par blocs** (`clé:` puis lignes indentées) comme ci-dessus : le parseur de repli sans PyYAML ne gère pas les mappings inline `{clé: valeur}`.

Rôles des clés :

- `entity_types` : types autorisés lors de l'extraction ; `folder` fixe le dossier vault (préfixe numérique libre) et `label` l'affichage dans les notes.
- `relation_types` : types autorisés ; `label` sert aux tableaux, aux arêtes Mermaid et aux libellés de canvas. Une relation non déclarée est **rejetée** par le parseur.
- `sections` : rôles sémantiques (`identity`, `facts`, `balance`, …) → titres en langue voulue. Les renderers ont des replais français si un rôle manque.
- `styles` : direction Mermaid, dimensions/grille des canvas, et type d'entité alimentant la chronologie macro. Valeurs par défaut raisonnables si une clé est absente.
- `vault` : dossier des arcs, note macro, titre macro, index racine. `blueprint.folder_for()` et `blueprint.relation_label()` sont les deux accès les plus utilisés par les renderers.

---

## 5. Étage 2 — `GraphEngine`

### 5.1 Ports, modèles et stockage

`graph_engine/ports.py` déclare `GraphStorePort` et réexporte `LlmPort` du hexagon du Scraper. `JsonGraphStore` implémente le port avec trois fichiers sous `--store-dir` :

| Fichier | Contenu |
|---|---|
| `graph.json` | `entities`, `relations`, `sources`, `analysis` (via `serialization.py`). |
| `manifest.json` | `chunk_id → SHA-256(texte)` des lots acquittés. |
| `extracted/<sha1(chunk_id)[:16]>.json` | `ExtractedBatch` mis en cache, un fichier par chunk du lot. |

Les écritures passent par `scraper.storage.write_json` (écriture atomique). Le graphe sérialisé est un **produit** ; `run()` ne le relit pas : le Reduce rejoue les lots mis en cache.

Modèles (`models.py`, `graph.py`) :

- `Entity(id, name, entity_type, aliases, attributes, facts)` ; `Fact(statement, source_id, arc_or_context)`.
- `Relation(source_id_entity, target_id_entity, relation_type, arc_or_context, dynamic_or_evolution, source_ids)` : lien typé, orienté et temporalisé (champ `evolution` du LLM).
- `UnresolvedRelation` : relation dont les extrémités sont encore des noms, résolue globalement en Reduce.
- `ExtractedBatch(chunk_ids, entities, relations, unresolved_relations)` : sortie d'un lot Map.
- `KnowledgeGraph(entities, relations, sources, analysis)` avec `neighbors(entity_id)` pour le voisinage à 1 saut.

### 5.2 Phase Map : extraction par lots

`extraction.py` construit un prompt qui injecte les **types déclarés** du blueprint et les chunks identifiés :

```text
[CHUNK <chunk_id>]
<texte du chunk>
[/CHUNK]
```

Le modèle doit répondre en JSON avec `entities` et `relations`. Chaque fait et chaque relation doivent porter le `source_id` du chunk d'origine ; `arc` nomme l'arc/context et `evolution` décrit le changement dans le temps.

Validation (`parsing.py`, `entity_parsing.py`) :

- JSON brut ou JSON dans une balise ```` ```json ```` accepté ; réponse invalide → lot vide.
- Entité retenue seulement si `type` est déclaré ; `id = stable_id("ent", type, canonical_key(name))`.
- Alias dédupliqués, attributs fusionnés, faits dont le `statement` est non vide.
- `source_id` vérifié : s'il n'appartient pas au lot, repli sur le premier `chunk_id` du lot (`valid_source_id`).
- Relation retenue seulement si `type` est déclaré. Si les deux extrémités sont trouvées dans le lot, elle est typée directement ; sinon, elle devient `UnresolvedRelation` si les deux noms sont présents et différents.

Un appel LLM qui lève une exception est attrapé : `extract_batch()` renvoie `None`, donc **aucun cache ni acquittement** n'est écrit. Le lot sera retenté au run suivant. `max_tokens` par appel est de 1500 (à distinguer du budget global `--max-tokens` de la CLI).

### 5.3 Cache et reprise incrémentale

`GraphEngine.run()` :

1. Calcule `current = {chunk_id: sha256(texte)}` et lit `manifest.json` du store.
2. Pour chaque chunk, `_cached_batch()` ne rejoue un lot que si **son hash correspond** et si **tous les chunks du lot** sont encore présents avec le même hash. Les lots rejoués sont dédupliqués par `tuple(sorted(chunk_ids))`.
3. Les chunks restants sont regroupés par `batch_size` (défaut 3) et envoyés au LLM.
4. Après chaque lot réussi, `save_extraction()` est appelé pour chaque chunk puis `save_manifest(acknowledged)` : une interruption ne refait pas les lots déjà acquittés.
5. Le graphe est reconstruit depuis **tous** les lots (cachés + nouveaux), analysé, puis `graph.json` et le manifeste final sont écrits.

Le manifeste final est reconstruit depuis les chunks actuellement présents et acquittés : un chunk supprimé de l'export disparaît donc du manifeste (ses fichiers `extracted/` restent mais ne sont plus rejoués).

### 5.4 Phase Reduce : alias, fusion, remap

`consolidation.py` orchestre trois opérations :

1. **Cluster d'entités** (`entity_merge.py`) : clés canoniques issues de `name` + `aliases` (`canonical_key`), avec variante singulière pour les clés > 4 caractères finissant par `s`. Deux clusters qui se recoupent sont fusionnés dans le premier (tri déterministe des indices). Le "gagnant" a le plus de faits, puis le nom le plus long ; ses alias, attributs et faits sont unis (faits dédupliqués par `(canonical_key(statement), source_id)`). Un `id_map` ancien ID → ID gagnant est retourné.
2. **Résolution des relations en attente** : une table `canonical_key → id` construite sur *toutes* les entités finales permet de transformer chaque `UnresolvedRelation` en `Relation`. `setdefault` fait gagner la première entité rencontrée ; les extrémités introuvables ou identiques sont ignorées.
3. **Fusion des relations** (`relation_merge.py`) : extrémités remappées via `id_map`, auto-boucles supprimées, déduplication par `(source, target, type, arc)`, union des `source_ids` et concaténation des évolutions avec ` | `.

Les entités finales sont triées par nombre de faits décroissant puis par nom, ce qui stabilise l'ordre des notes générées ensuite.

### 5.5 Analyse : centralité, communautés, ponts

`analysis.py` construit une adjacency **non orientée pondérée** (une relation ajoute un poids dans chaque sens).

- **Centralité** : degré pondéré `/ (N - 1)` ; `0.0` si le graphe a moins de deux entités. Les cinq pivots sont affichés en note macro.
- **Communautés** : optimisation greedy de la modularité (phase 1 de Louvain), déterministe : nœuds triés, une communauté par nœud, déplacements tant qu'un gain > `1e-12` existe, départage lexicographique. Le label d'une communauté est l'arc le plus fréquent dans les faits et relations internes (départage alphabétique), sinon le nom du pivot le plus central.
- **Ponts** : toute relation dont les extrémités appartiennent à deux communautés différentes.

Cette approche garde séparés les groupes densément liés même lorsqu'un ou deux ponts les relient (une simple propagation de labels les fusionnerait).

### 5.6 Sortie

`GraphEngine.run()` retourne le `KnowledgeGraph`, avec `graph.analysis` renseigné. `graph.json` est écrit via `graph_to_dict()`. L'étage 2 ne sait rien d'Obsidian : il ne crée aucun dossier vault et ne génère aucune note.

---

## 6. Étage 3 — `ObsidianSynthesizer`

### 6.1 Port, planification et sécurité du vault

`VaultExporterPort` expose `read_note`, `write_note`, `list_notes`. `ObsidianVaultExporter` implémente le port sur le système de fichiers :

- tout chemin relatif est résolu puis vérifié avec `is_relative_to(root)` (protection contre `../`) ;
- `write_note` passe par un fichier `.tmp` puis `os.replace` (écriture atomique) ;
- `list_notes` énumère les `*.md`.

`planning.py::build_plans()` produit une `NotePlan` par fichier cible :

| Plan | Chemin | Contenu du `payload` (clé de hash) |
|---|---|---|
| Micro | `<folder>/<slug(name)>.md` (suffixe `-<id[-6:]>` en cas de collision) | entité, relations voisines, extraits sources, sections micro, libellés, direction Mermaid. |
| Méso | `<arcs_folder>/arc-<id>-<slug(label)>.md` | communauté, membres, relations internes, sources, sections méso, chemin canvas. |
| Canvas d'arc | même stem + `.canvas` | graphe JSON `{nodes, edges}` de la communauté. |
| Macro | `vault.macro_note` | compteurs, centralité, communautés, ponts, noms, arcs, sections macro, titre, type chronologie. |
| Canvas macro | `macro_note` sans `.md` + `.canvas` | groupes par communauté + arêtes de pont. |
| Index | `<folder>/_Index.md` et `vault.root_index` | listes de wikilinks (`{"entries": …}` / `{"links": …}`). |

### 6.2 Niveau micro — une note par entité

`notes_micro.py` rend, dans l'ordre :

1. Frontmatter : `id`, `type`, `aliases`, `tags`, `sources_count`, `content_hash`, `locked` (ajouté à `false` à la création).
2. `## Identité` : libellé du type, alias, attributs triés.
3. `## Faits établis` : chaque fait, son arc entre parenthèses et son `source_id` entre backticks.
4. `## Relations` : tableau `Cible | Nature du lien | Évolution | Arcs communs`, avec wikilink vers l'autre entité, libellé du blueprint, évolution (ou `—`) et arcs partagés.
5. Bloc ```mermaid : voisinage à 1 saut (`graph <direction>`), nœuds déclarés puis arêtes `-->|libellé|`.
6. Callout `> [!cite]- Sources` : un extrait de 300 caractères par `source_id` unique, avec titre du document ou URL.

### 6.3 Niveau méso — une note par communauté

`notes_meso.py` rend l'embed `![[<canvas>.canvas]]`, la liste des membres (`[[Nom]] (Type)`), les interactions internes (`[[A]] → [[B]] : libellé *(arc)* — évolution : …`), les enjeux groupés par arc avec les faits sourcés, puis le callout de sources.

### 6.4 Niveau macro — vue globale et canvas

`notes_macro.py` rend :

- `Vue d'ensemble` : compteurs entités/relations/communautés/sources, liens vers les notes d'arc, cinq pivots de centralité ;
- `Grands équilibres` : tableau `Communauté | Membres | Liens internes | Ponts` ;
- `Chronologie maîtresse` : arcs identifiés, plus les entités du type `styles.timeline_entity_type` si déclaré ;
- `Ponts entre arcs` : chaque relation inter-communautés avec son libellé et son arc.

`canvas.py` génère un JSON Obsidian valide :

- canvas d'arc : nœuds `type: file` disposés en grille (`canvas_columns`, largeur/hauteur du blueprint, espacement 40) et arêtes étiquetées ;
- canvas macro : nœuds `type: group` par communauté contenant les nœuds fichiers, puis arêtes pour les ponts.

Les canvas sont écrits tels quels (JSON) : ni frontmatter ni autolinking.

### 6.5 Autolinks et frontmatter

`autolink.py` transforme les mentions connues en `[[Nom officiel]]` ou `[[Nom officiel|Alias surfacé]]` :

- surfaces = noms + alias de toutes les entités, sauf la note elle-même (`self_name`) ;
- tri par longueur décroissante pour éviter les correspondances partielles, recherche insensible à la casse ;
- zones protégées : frontmatter, titres `#`, blocs de code fence, code inline, wikilinks déjà présents ;
- désactivé (`apply_autolink=False`) pour les canvas et les index, qui construisent déjà leurs liens explicitement.

`frontmatter.py` implémente un sous-ensemble YAML suffisant (scalaires, booléens, entiers, listes en ligne) pour rendre et relire les champs gérés, sans dépendance externe.

### 6.6 Synchronisation incrémentale et verrouillage

`synthesizer.py` applique, pour chaque `NotePlan` :

1. `digest = content_hash(plan.payload)` : SHA-256 de `json.dumps(payload, sort_keys=True, ensure_ascii=False)`.
2. Lecture de la note existante et de `.synthesizer/manifest.json` (`chemin → hash`).
3. Décision :

| Situation | Action | Rapport |
|---|---|---|
| Note existante avec `locked: true` | Jamais réécrite ; hash précédent conservé si présent | `report.locked` |
| Hash du manifeste identique | Aucune écriture | `report.up_to_date` |
| Sinon | Écriture de la note (frontmatter + corps, ou JSON pour un canvas) et du nouveau hash | `report.written` |

4. `save_manifest()` réécrit le manifeste avec uniquement les plans courants : les notes supprimées du plan disparaissent du manifeste.

Un utilisateur peut poser `locked: true` dans le frontmatter d'une note Obsidian : elle restera intacte quoi que change le graphe. `SynthesisReport` expose les trois catégories, affichées par la CLI.

---

## 7. Lancement

```powershell
python -m warframe_lore.v1.aval_cli `
  --export-dir <dossier run-*> `
  --blueprint warframe_lore/v1/configs/blueprint.example.yaml `
  --store-dir <dossier graphe> `
  --vault-dir <vault Obsidian> `
  --endpoint http://127.0.0.1:1234/v1 --model <nom-du-modele>
```

Options : `--max-calls` (200), `--max-tokens` (100 000) et `--batch-size` (3) contrôlent le budget et le regroupement Map. `--endpoint` pointe par défaut sur LM Studio local ; tout service compatible OpenAI convient.

Sans `--model`, l'adapter retourne une réponse vide : aucun appel réseau, graphe sans entités ; seules la note macro, son canvas et l'index racine sont produits. **Piège** : ces extractions vides sont acquittées et mises en cache. Pour repasser avec un modèle, utilisez un `--store-dir` neuf ou supprimez `manifest.json` et `extracted/`.

Usage programmatique équivalent :

```python
from pathlib import Path
from warframe_lore.v1.aval_cli import main

main([
    "--export-dir", str(Path("exports/mon-univers/run-001")),
    "--blueprint", "warframe_lore/v1/configs/blueprint.example.yaml",
    "--store-dir", "out/graph",
    "--vault-dir", "out/vault",
    "--model", "mon-modele-local",
])
```

Les classes sont aussi composables directement (`GraphEngine(blueprint, llm, store)` puis `ObsidianSynthesizer(blueprint, exporter)`), ce qui permet d'injecter un faux LLM ou un faux vault en mémoire.

---

## 8. Tests et validation

- `tests/v1/test_graph_engine_contract.py` : contrat étage 2 — extraction/fusion d'alias, relations typées/temporalisées, résolution inter-lots, communautés/ponts, reprise incrémentale et non-acquittement d'un échec LLM.
- `tests/v1/test_synthesizer_contract.py` : contrat étage 3 — wikilinks, Mermaid, canvas JSON, notes Micro/Méso/Macro, sync incrémentale et protection `locked: true`.
- `tests/v1/aval_fakes.py` : fakes partagés et mini-univers fictif générique « Chronicles of Aurelia » (aucune donnée d'un univers réel).

Commandes de contrôle :

```powershell
uv run ruff check
uv run pytest
```

---

## 9. Points d'attention

- Un écart de `sha256` entre `chunks.jsonl` et le manifeste du Scraper est **averti**, pas bloquant.
- `graph.json` n'est pas la source du Reduce : si le cache `extracted/` est supprimé mais que `manifest.json` subsiste, les lots redeviennent `missing` et sont ré-extraits.
- Les relations dont le type n'est pas déclaré dans le blueprint sont silencieusement écartées ; vérifiez le blueprint avant de conclure à une perte d'information.
- Sans `styles.timeline_entity_type`, la chronologie macro se limite aux arcs trouvés dans les faits.
- L'analyse est en Python pur et adaptée à des graphes à échelle entité ; elle n'a pas vocation à remplacer un moteur de graphe pour des millions de nœuds.
- Les deux étages sont indépendants du Scraper v1 : toute évolution du schéma d'export (`chunks.jsonl`, `documents.jsonl`) se répercute d'abord dans `graph_engine/documents.py`.
