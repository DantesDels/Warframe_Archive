# Rapport d'audit technique : Cephalon Archive

**L'enjeu prioritaire est la fidélité des données, avant l'optimisation vectorielle ou la conteneurisation.** Plusieurs comportements actuels peuvent conserver des archives obsolètes, classer une spéculation comme canon ou produire un parcours KIM incorrect.

Audit du commit `28baaab`, branche locale `dev`, sans modification du projet pendant l'audit. Les exemples ci-dessous sont des corrections proposées, pas des changements appliqués.

## Constats prioritaires

`P1` : à corriger avant de considérer le corpus fiable pour un RAG. `P2` : robustesse, sécurité ou UX à traiter avant une diffusion plus large. Aucun incident de compromission n'a été constaté.

### 1. P1 : La synchronisation SQL/JSON peut diverger

Références : [scraper.py:173](warframe_lore/scraper.py#L173), [scraper.py:281](warframe_lore/scraper.py#L281), [writer.py:55](warframe_lore/output/writer.py#L55), [manager.py:295](warframe_lore/db/manager.py#L295).

Le traitement actuel suit cet ordre :

```text
Écriture SQL → validation du delta SQL → publication JSON du bucket
```

Si la publication JSON échoue, le prochain lancement considère néanmoins la page comme synchronisée. Le JSON peut rester ancien indéfiniment.

Deux problèmes connexes existent :

- La fusion JSON est additive : une page retirée d'un bucket reste dans son ancien megafile.
- `purge_vanished_pages()` efface l'état de synchronisation, pas la page SQL ni ses dérivés.

**Correction minimale :** acquitter la synchronisation seulement après publication réussie, et réconcilier les affectations avec un inventaire complet.

**Architecture préférable :** PostgreSQL devient la source de vérité ; les megafiles deviennent une projection régénérable, indépendamment du delta réseau.

```python
# Pseudocode : contrats proposés, absents actuellement.
async with repository.transaction() as tx:
    await tx.upsert_page(page)
    await tx.record_revision(page)
    await tx.mark_bucket_dirty(bucket_id)

# Exécuté aussi lorsqu'aucune page ne nécessite de téléchargement.
for bucket_id in await repository.dirty_buckets():
    snapshot = await repository.bucket_snapshot(bucket_id)
    publisher.publish_atomically(snapshot)
    await repository.mark_published(bucket_id, snapshot.revision)
```

Le marquage final doit être conditionné à la révision publiée : une modification concurrente ne doit pas être acquittée par erreur.

Pour les disparitions, choisir explicitement entre suppression du corpus courant et conservation historique avec `retired_at`. Ne jamais déduire une suppression d'une résolution de catégories partielle ou échouée.

### 2. P1 : Le classement canonique contredit son contrat

Références : [output/models.py:34](warframe_lore/output/models.py#L34), [scraper.py:106](warframe_lore/scraper.py#L106), [cleaner/pipeline.py:199](warframe_lore/cleaner/pipeline.py#L199).

Trois défauts sont identifiés :

- Les priorités augmentent avec l'incertitude, mais `merge_canon_status()` utilise `min()`.
- La présence simultanée de signaux canon et spéculatif aboutit à `canon`.
- Les templates spéculatifs imbriqués ne sont pas détectés par le parcours de premier niveau.

Résultat reproduit :

```python
merge_canon_status(CanonStatus.CANON, CanonStatus.SPECULATION)
# Actuel : CanonStatus.CANON
```

Corrections ciblées :

```python
# output/models.py : conserver le traitement existant du cas vide.
return max(present, key=lambda status: _CANON_PRIORITY[status])

# scraper.py
if page_level_speculative or inline_non_canon:
    return CanonStatus.SPECULATION
return CanonStatus.CANON

# pipeline.py : détecter avant de remplacer/aplatir les templates.
non_canon_detected = any(
    must_flag_non_canon(node, self.cleaner_config)
    for node in parsed.filter_templates(recursive=True)
)
```

À terme, une page peut contenir plusieurs niveaux de fiabilité. Conserver un statut prudent au niveau page et une provenance précise par section/chunk évitera de rejeter tout un article pour un seul passage spéculatif.

### 3. P1 : Le graphe KIM perd sa sémantique

Références : [cleaner/pipeline.py:144](warframe_lore/cleaner/pipeline.py#L144), [chunker.py:43](warframe_lore/db/chunker.py#L43), [server.py:747](warframe_lore/ui/server.py#L747), [app.js:775](warframe_lore/ui/static/app.js#L775).

Les conditions `{If ...}`, marqueurs `{P1}` et certains renvois sont supprimés **avant stockage**. Ce qui devait être masqué en mode RP disparaît donc aussi de la représentation exploitable par le RAG.

Le graphe reconstruit comporte également des erreurs vérifiées :

- Un choix terminal reçoit une arête vers la réplique suivante.
- Une arête directe PNJ → PNJ permet de contourner les choix.
- Le simulateur ignore `option.ends`.
- Une étape portant `jump_to` est sautée avant affichage de sa propre réplique.

**Correction architecturale : parser une fois, produire plusieurs vues.**

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class DialogueNode:
    id: str
    speaker: str | None
    text: str
    conditions: tuple[str, ...]
    next_ids: tuple[str, ...]
    terminal: bool
```

La vue RP affiche `text`. Le simulateur et le RAG utilisent aussi `conditions` et `next_ids`. Les destinations non résolues doivent être signalées, pas remplacées silencieusement par un flux séquentiel.

Invariants à imposer :

```python
assert all(edge["target"] in nodes_by_id for edge in edges)
assert not any(
    nodes_by_id[edge["source"]].terminal
    for edge in edges
)
```

Correctif immédiat du choix terminal :

```javascript
appendSimBubble({ ...option, speaker: "", player: true });
if (option.ends) {
  simEnd();
  return;
}
kimSimState.cursor++;
simNext();
```

Cela ne suffit pas à reconstruire les branches perdues. Les pages déjà nettoyées devront être retraitées depuis une source conservant leurs annotations.

### 4. P1 : Le chunking dialogue ne respecte pas toujours ses bornes

Référence : [chunker.py:218–256](warframe_lore/db/chunker.py#L218).

Une réplique synthétique de 6 012 caractères produit :

```text
[2500, 2500, 1512, 6012]
```

Elle est découpée, puis réémise intégralement. Placée après une courte réplique, elle contourne le fallback et reste entière.

**Nuance :** ce défaut n'a pas été déclenché par les 843 chunks KIM recalculés sur le corpus local ; leur maximum observé est 2 499 caractères.

Traiter les longues lignes avant le débordement ordinaire corrige les deux chemins :

```python
# À placer avant le traitement ordinaire de la ligne.
if len(line) > max_characters:
    if chunk_lines:
        chunks.append(RAGChunk(
            len(chunks), "\n".join(chunk_lines),
            _speakers_metadata(per_chunk_speakers),
        ))

    for piece in _hard_split(line, max_characters, overlap_characters):
        chunks.append(RAGChunk(
            len(chunks), piece,
            _speakers_metadata([speaker] if speaker else []),
        ))

    chunk_lines, per_chunk_speakers, current_size = [], [], 0
    continue
```

Autres limites du mode dialogue : il court-circuite la passe par titres et n'applique pas de chevauchement textuel entre les chunks ordinaires. Les locuteurs, eux, s'accumulent, même lorsqu'ils ne figurent plus dans le texte émis.

La correction durable consiste à découper d'abord par conversation/section, puis par tours de parole, avec un chevauchement de tours réellement conservés.

### 5. P1 : Une regex présente un coût polynomial élevé

Références : [cleaner/pipeline.py:88](warframe_lore/cleaner/pipeline.py#L88), avec variantes dans `chunker.py`, `server.py` et `app.js`.

Le préfixe suivant permet plusieurs répartitions concurrentes des mêmes espaces :

```regex
^>\s*\*{0,3}\s*>?\s*
```

Sur l'entrée `">" + " " * n + "X"`, le nettoyage complet a pris environ :

| Espaces | Temps |
|---:|---:|
| 100 | 0,006 s |
| 200 | 0,035 s |
| 400 | 0,275 s |

La croissance est compatible avec un coût cubique. C'est un risque crédible de blocage sur contenu wiki adversarial, **pas une preuve d'attaque constatée**.

Remplacer le préfixe ambigu par :

```python
prefix = (
    r"(?im)^>[ \t]*"
    r"(?:\*{1,3}[ \t]*)?"
    r"(?:>[ \t]*)?"
)
```

Les espaces optionnels suivent alors un marqueur effectivement consommé. Ajouter des tests sur les quatre variantes et des budgets de taille d'entrée.

Plus généralement, employer l'AST pour les structures imbriquées et réserver les regex aux transformations locales. Par exemple, l'ordre actuel enlève les balises HTML avant de supprimer certains blocs de code ; leur contenu subsiste. Correction immédiate :

```python
text = strip_wikitext_comments(wikitext)
text = strip_tables_and_code_blocks(text)
text = convert_html_tags(text)
```

### 6. P1 : Le Public Export n'est pas vérifié comme annoncé

Références : [export.py:37](warframe_lore/export.py#L37), [export.py:64](warframe_lore/export.py#L64), [export.py:159](warframe_lore/export.py#L159).

La séparation des responsabilités est correcte :

```text
Origin HTTPS → index compressé
Content      → manifests désignés par l'index
```

En revanche :

- Les manifests sont téléchargés en **HTTP**.
- Le suffixe hash sert de clé de cache ; aucune vérification des octets contre ce digest n'est effectuée.
- Un cache existant est accepté sans validation et écrit directement avant parsing.
- Un index LZMA tronqué peut produire un nom incomplet accepté comme asset.

Exemple reproduit après troncature d'un flux synthétique :

```text
ExportWeapons_en.json!00_
```

**Le nom content-addressed n'est pas, à lui seul, une preuve d'intégrité.**

Correction du contrat de téléchargement :

```python
# Pseudocode : validation obligatoire avant publication du cache.
payload = fetch_authenticated(asset_url)
document = json.loads(payload.decode("utf-8"))

if not isinstance(document, dict):
    raise ValueError("Manifest invalide")
if not isinstance(document.get(category), list):
    raise ValueError("Categorie absente ou invalide")

verify_provider_digest(payload, expected_digest)
atomic_cache_write(cache_path, payload)
```

`verify_provider_digest()` nécessite de documenter l'algorithme réel du fournisseur ; il ne faut pas supposer arbitrairement SHA-256. Le support HTTPS de l'endpoint Content doit également être vérifié avant modification, ce qui n'a pas été fait pendant cet audit.

Pour LZMA, une politique stricte bornée serait :

```python
limit = 2 * 1024 * 1024  # Budget d'index à calibrer.
decoder = lzma.LZMADecompressor(
    format=lzma.FORMAT_ALONE,
    memlimit=64 * 1024 * 1024,
)
decoded = decoder.decompress(raw, max_length=limit + 1)
if len(decoded) > limit or not decoder.eof:
    raise ValueError("Index trop grand ou incomplet")
```

Si l'absence d'EOF est une particularité fournisseur confirmée, prévoir une exception explicite avec validation des lignes complètes et des catégories attendues, plutôt qu'accepter indistinctement tout préfixe décodé.

### 7. P1 : La persistance RAG est incomplète et destructive

Références : [models.py:96](warframe_lore/db/models.py#L96), [manager.py:158](warframe_lore/db/manager.py#L158), [init_db.sql:72](init_db.sql#L72).

**Manque fonctionnel :** `embedding vector(384)` existe, mais le pipeline audité ne calcule ni n'insère de vecteurs. Aucune recherche vectorielle n'est raccordée à l'interface.

**Défaut de cycle de vie :** chaque upsert supprime et recrée les chunks. Tout embedding ajouté extérieurement serait perdu, même pour un texte inchangé.

Préserver les enrichissements seulement lorsque leur entrée reste identique :

```sql
-- Fragment d'upsert des chunks.
ON CONFLICT (wiki_page_id, chunk_index) DO UPDATE
SET content_markdown = EXCLUDED.content_markdown,
    metadata = EXCLUDED.metadata,
    embedding = CASE
      WHEN lore_chunks.content_markdown
             IS DISTINCT FROM EXCLUDED.content_markdown
        OR lore_chunks.metadata IS DISTINCT FROM EXCLUDED.metadata
      THEN NULL
      ELSE lore_chunks.embedding
    END;
```

Supprimer ensuite les indices disparus. À terme, comparer l'empreinte du texte réellement encodé et la version du modèle, plutôt que toutes les métadonnées.

**Divergence ORM/DDL :** le SQL déclare GIN, HNSW et l'unicité du titre ; les modèles ne les reproduisent pas. Ce n'est pas une preuve que la base déployée manque d'index, mais deux modes d'initialisation peuvent produire deux schémas différents.

```python
Index("idx_wiki_pages_title", WikiPage.page_title, unique=True)
Index("idx_chunks_metadata", LoreChunk.__table__.c.metadata,
      postgresql_using="gin")
Index("idx_chunks_embedding", LoreChunk.embedding,
      postgresql_using="hnsw",
      postgresql_ops={"embedding": "vector_cosine_ops"})
```

Une procédure de migrations versionnées doit devenir la référence, avec test de cohérence du modèle.

### 8. P2 : Le bootstrap frontend réinstalle les événements

Références : [app.js:1110](warframe_lore/ui/static/app.js#L1110), [app.js:1178](warframe_lore/ui/static/app.js#L1178), [app.js:554](warframe_lore/ui/static/app.js#L554).

Le bouton Recharger rappelle `init()`, qui ajoute de nouveaux listeners anonymes aux éléments persistants. Après un rechargement, le burger peut effectuer deux inversions successives et sembler ne plus fonctionner.

Correction minimale :

```javascript
$("#btn-reload").addEventListener("click", () => {
  window.location.reload();
});
```

Pour un rafraîchissement sans navigation, séparer installation unique des événements et rechargement des données.

Les rendus asynchrones présentent aussi une course : ouvrir A puis B peut laisser une réponse tardive de A écraser le contenu de B.

```javascript
let routeEpoch = 0;

function handleRoute() {
  const epoch = ++routeEpoch;
  // Transmettre epoch au rendu choisi par le routeur.
}

async function renderPage(bucketId, title, epoch) {
  const page = await api(
    `/api/page?bucket=${encodeURIComponent(bucketId)}&title=${encodeURIComponent(title)}`
  );
  if (epoch !== routeEpoch) return;
  // Appliquer le rendu uniquement après cette garde.
}
```

Appliquer le même principe aux erreurs, suggestions et changements d'onglets, avec annulation éventuelle via `AbortController`. Une migration Vue ne supprimerait pas automatiquement ces courses.

### 9. P2 : Le cache ne garantit ni cohérence ni fraîcheur

Références : [server.py:103](warframe_lore/ui/server.py#L103), [app.js:62](warframe_lore/ui/static/app.js#L62).

Le serveur recharge tous les fichiers à échéance sans verrou et publie `_buckets` puis `_pages` séparément. Des requêtes concurrentes peuvent travailler sur des générations différentes.

Inversement, le navigateur conserve les réponses dans une `Map` sans expiration : `Cache-Control: no-store` ne purge pas ce cache applicatif.

Contrat serveur recommandé :

```python
# Pseudocode : les lecteurs capturent une seule référence.
with self._reload_lock:
    if time.monotonic() < self._next_reload:
        return
    snapshot = self._read_validated_snapshot()
    self._snapshot = snapshot
    self._next_reload = time.monotonic() + 5
```

Conserver le dernier snapshot valide en cas d'échec. Pour garantir la cohérence entre plusieurs megafiles, publier une génération complète puis basculer un manifeste de référence.

Correction client minimale :

```javascript
const hit = apiCache.get(path);
if (cache && hit && hit.expiresAt > performance.now()) {
  return hit.data;
}

// Après réception :
apiCache.set(path, {
  data,
  expiresAt: performance.now() + 5000,
});
```

Il faut aussi invalider `state.stats`, les buckets et les caches KIM. Une version de corpus partagée est plus fiable qu'une accumulation de TTL indépendants.

### 10. P2 : Les frontières HTTP/HTML sont à durcir

Références : [server.py:833](warframe_lore/ui/server.py#L833), [server.py:918](warframe_lore/ui/server.py#L918), [app.js:115](warframe_lore/ui/static/app.js#L115).

Le serveur écoute uniquement sur `127.0.0.1`, ce qui réduit fortement l'exposition actuelle. Néanmoins :

- `limit=-1` est accepté et renvoie presque tous les résultats.
- Les threads et le coût des recherches ne sont pas plafonnés.
- `Access-Control-Allow-Origin: *` autorise les lectures inter-origines lorsque le navigateur permet l'accès au service local.
- Le rendu Markdown ne filtre pas les protocoles des liens.

Premiers garde-fous :

```python
limit = max(1, min(_int_from_query(query, "limit", 50), 200))
if len(query_text) > 256:
    self.send_error(400, "Query too long")
    return
```

Pour le lancement local actuel, contrôler `Host`/`Origin` avant le traitement et retirer le wildcard CORS. Une configuration de déploiement devra définir explicitement ses origines autorisées.

Pour les liens, utiliser un parseur Markdown avec rendu contrôlé ; à défaut, construire les liens depuis des tokens validés :

```javascript
function safeLink(label, href) {
  let url;
  try { url = new URL(href, location.origin); }
  catch { return document.createTextNode(label); }

  if (!["http:", "https:"].includes(url.protocol)) {
    return document.createTextNode(label);
  }
  const a = document.createElement("a");
  a.textContent = label;
  a.href = url.href;
  a.target = "_blank";
  a.rel = "noopener noreferrer";
  return a;
}
```

Aucune exécution XSS n'a été démontrée. Aucun traversal exploitable n'a été confirmé : les routes statiques sont fixes et les médias passent par une liste de noms générés.

### 11. P2 : Recherche, accessibilité et spoilers restent inachevés

Références : [app.js:1034](warframe_lore/ui/static/app.js#L1034), [app.js:1230](warframe_lore/ui/static/app.js#L1230), [styles.css:879](warframe_lore/ui/static/styles.css#L879), [app.js:547](warframe_lore/ui/static/app.js#L547).

**Recherche :** après apparition des suggestions, Enter ne fait rien si aucune suggestion n'est sélectionnée, car l'index vaut `-1`.

```javascript
if (event.key === "Enter") {
  event.preventDefault();
  if (dropdownIndex >= 0) {
    activateDropdown();
    return;
  }
  hideDropdown();
  navigate("search");
  runSearch();
  searchInput.blur();
}
```

**Accessibilité :** les résultats et cartes sont des `div` cliquables. Employer des liens natifs :

```javascript
const item = el("a", "page-list-item");
item.href = `#page?${encodeURIComponent(bucketId)}?${encodeURIComponent(title)}`;
```

Sur mobile, rendre la sidebar fermée `inert`, gérer Escape et restituer le focus au burger. Le rail tablette masque actuellement les libellés des buckets ; supprimer ce rail incomplet est préférable à des boutons vides.

**Spoilers :** le code affiche un avertissement mais insère immédiatement le contenu. Un premier bloc accessible peut être natif :

```javascript
function spoilerBlock(body, reason) {
  const box = el("details", "spoiler-block");
  box.append(el("summary", null, `Afficher le spoiler : ${reason}`), body);
  return box;
}
```

Appliquer la même politique aux snippets, au simulateur et au montage du graphe. Il s'agit d'un contrôle UX, pas d'une barrière de sécurité.

## Stack réelle

Plusieurs éléments du contexte décrivent une cible plutôt que l'implémentation présente.

| Élément annoncé | État constaté |
|---|---|
| Frontend Vue Composition API | Application principale en JavaScript natif ; Vue utilisé pour le flowchart |
| Tailwind CSS | CSS personnalisé, sans chaîne Tailwind versionnée |
| `MarkdownHeaderTextSplitter` / `RecursiveCharacterTextSplitter` | Équivalents maison, sans LangChain |
| PostgreSQL + pgvector | Schéma présent ; production et retrieval des embeddings non raccordés |
| Graphe de dialogue JSONB | JSONB pour les métadonnées des chunks ; messages KIM relationnels ; graphe reconstruit en mémoire |
| Vérification de hash Public Export | Cache par nom haché, sans vérification cryptographique du contenu |
| `<SpoilerBlock>` dynamique | Avertissement, sans composant de masquage opérationnel |
| Docker | Commande documentée pour PostgreSQL ; pas de Dockerfile/Compose versionné |

Ce n'est pas un problème d'utiliser du JavaScript natif ou un splitter maison. Le problème est l'écart entre les garanties annoncées et celles réellement testées.

## Architecture et flux

Les bases à conserver sont bonnes : modules séparés, modèles de données explicites, transactions SQL par page, remplacement atomique des fichiers JSON et identité i18n `(entity_id, lang)`.

La cible raisonnable reste un **monolithe modulaire**, pas un ensemble prématuré de microservices :

```text
MediaWiki / Public Export
          |
          v
Sources brutes versionnées + provenance
          |
          v
Parsing structurel : lore / dialogue / entité
          |
          v
PostgreSQL : état courant + historique utile
          |
          +--> Chunks --> embeddings --> retrieval
          +--> Graphe validé --> simulateur / Vue Flow
          +--> Megafiles versionnés --> lecture locale
```

**SOLID utile, sans surarchitecture :**

- **SRP :** le parser produit une structure métier ; le renderer décide ce qui est visible.
- **DRY :** un seul parseur KIM doit alimenter SQL, graphe, simulateur et RAG.
- **DIP :** injecter source, cleaner et repository au lieu de les construire obligatoirement dans `Scraper`.
- **KISS :** conserver PostgreSQL et un worker simple ; Redis, Kafka ou une base graphe ne sont pas encore justifiés.

Exemple d'injection minimale, en réutilisant `BaseSource` :

```python
def __init__(self, config, *, source=None, cleaner=None):
    self.config = config
    self.source = source if source is not None else MediaWikiSource(config)
    self.cleaner = cleaner if cleaner is not None else WikitextCleaner()
```

**Goulots identifiables :**

Le delta relit l'état complet d'un bucket pour chaque page : pour un bucket de `N` pages, cela représente `N` requêtes et potentiellement `N²` enregistrements transférés. Charger l'état une fois suffit :

```python
states = {
    spec.id: await self.db.fetch_sync_state(spec.id)
    for spec in self.buckets.specs
}
stored = states[bucket_id].get(page_title)
fresh = stored is not None and stored["touched"] == touched
```

GIN et HNSW existent dans le DDL. Leur coexistence ne garantit cependant pas un filtrage avant ANN. Par exemple, privilégier une expression compatible avec le GIN existant :

```sql
WHERE metadata @> '{"speakers":["Amir"]}'::jsonb
```

Aucun goulot PostgreSQL n'a été mesuré : il faudra examiner les plans et le rappel sous filtres sur une base de test. JSONB n'est pas intrinsèquement problématique ; un gros graphe intégral réécrit à chaque modification pourrait le devenir. Des nœuds/arêtes relationnels avec conditions JSONB constituent une évolution possible, pas une nécessité immédiate.

## Optimisation RAG

La priorité n'est pas simplement d'augmenter les chunks. Elle est de récupérer des **preuves cohérentes et typées**.

| Contenu | Unité recommandée | Contexte à récupérer |
|---|---|---|
| Lore | Section puis chunks sous budget tokenizer | Titre, hiérarchie, section parente |
| Dialogue | Tours de parole d'une branche compatible | Conversation, conditions, choix précédent, voisins pertinents |
| Statistiques | Données structurées d'une entité | Identifiant officiel, version du jeu/export, unités |

Les statistiques numériques sont actuellement écartées par l'extraction i18n, qui conserve surtout nom et description : [export.py:210](warframe_lore/export.py#L210). Ne pas attendre du modèle qu'il reconstruise des valeurs absentes.

Une extension simple préserverait les données techniques séparément :

```sql
CREATE TABLE game_entity_snapshot (
    entity_id   TEXT NOT NULL,
    export_hash TEXT NOT NULL,
    stats       JSONB NOT NULL,
    PRIMARY KEY (entity_id, export_hash)
);
```

**FR/EN : joindre sur l'identifiant officiel, jamais sur un nom traduit.**

```sql
SELECT en.entity_id, en.name AS name_en, fr.name AS name_fr
FROM game_entities_i18n en
LEFT JOIN game_entities_i18n fr
  ON fr.entity_id = en.entity_id AND fr.lang = 'fr'
WHERE en.lang = 'en';
```

Associer ensuite explicitement pages wiki et entités. Les titres affichés simplifiés ne doivent pas devenir des identifiants.

**Retrieval recommandé :**

1. Résoudre langue, entités, type de question et politique canon/spoiler.
2. Combiner correspondances lexicales et vectorielles.
3. Fusionner les rangs, puis éventuellement reranker.
4. Étendre les résultats vers la section parente ou les voisins de branche compatibles.
5. Produire une réponse citée, avec abstention si les preuves manquent.

Requête vectorielle minimale, une fois les embeddings alimentés :

```sql
SELECT c.id, c.content_markdown, c.metadata, p.source_url
FROM lore_chunks c
JOIN wiki_pages p ON p.page_id = c.wiki_page_id
WHERE c.embedding IS NOT NULL
  AND p.canon_status = :canon_status
ORDER BY c.embedding <=> CAST(:query_vector AS vector(384))
LIMIT :k;
```

Le modèle choisi doit réellement produire 384 dimensions. Versionner modèle, tokenizer, entrée encodée et pipeline ; ne pas mélanger leurs espaces vectoriels.

Une fusion RRF évite de comparer directement des scores incompatibles :

```python
from collections import defaultdict

scores = defaultdict(float)
for ranking in (lexical_ids, vector_ids):
    for rank, chunk_id in enumerate(ranking, start=1):
        scores[chunk_id] += 1 / (60 + rank)

selected = sorted(scores, key=scores.get, reverse=True)[:20]
```

Pour KIM, ne pas développer tous les chemins possibles : utiliser des fenêtres locales compatibles avec les conditions, sinon le nombre de parcours peut exploser.

## Évolutions majeures

Je recommande quatre investissements, dans cet ordre.

### 1. Ingestion rejouable

Conserver les sources brutes et identifier chaque dérivé par révision et version de pipeline. La publication rejouable du constat 1 permet de réparer une projection sans retélécharger le wiki.

```python
derivation_key = (
    source_id,
    source_revision,
    cleaner_version,
    chunker_version,
    embedding_model_version,
)
```

Le suivi doit distinguer téléchargé, validé, parsé, indexé et publié. Ajouter compteurs d'échecs, durées et état partiel explicite.

### 2. Tests et évaluation

Aucune suite de tests ni CI versionnée n'a été trouvée. Commencer par les invariants qui protègent les données :

```python
def test_long_dialogue_respects_budget():
    chunks = ChunkManager().split(
        "> **Amir:** " + "A" * 6000, is_dialogue=True,
    )
    assert all(len(c.content_markdown) <= 2500 for c in chunks)

def test_speculation_wins():
    assert merge_canon_status(
        CanonStatus.CANON, CanonStatus.SPECULATION,
    ) == CanonStatus.SPECULATION
```

Compléter avec tests de reprise après échec JSON, branches terminales, réponses réseau inversées et navigation clavier. Pour le RAG : jeu de questions FR/EN, Recall@k, fidélité des citations, contradictions entre branches et latence p95.

### 3. Livraisons reproductibles

Versionner dépendances verrouillées, recette du bundle Vue Flow, migrations et Compose de test. Le bundle actuel est livré sans recette de reconstruction versionnée.

Un autre défaut de distribution est visible : `cleaner_config.json` et `init_db.sql` sont cherchés hors du paquet. Après déplacement dans des ressources embarquées :

```python
from importlib.resources import files

root = files("warframe_lore").joinpath("resources")
cleaner_json = root.joinpath("cleaner_config.json").read_text(encoding="utf-8")
schema_sql = root.joinpath("init_db.sql").read_text(encoding="utf-8")
```

Tester une wheel hors checkout. Pour Docker : utilisateur non-root, volumes persistants, healthchecks, secrets externes et image PostgreSQL/pgvector figée. Une exposition réseau nécessitera aussi de remplacer ou durcir le serveur HTTP local actuel.

### 4. Lecture hors ligne

Une PWA est pertinente pour une archive. Elle doit distinguer ressources applicatives, données versionnées et images.

Exemple de stratégie Workbox, bibliothèque à introduire explicitement :

```javascript
registerRoute(
  ({ url }) => url.origin === self.location.origin
    && /^\/api\/(page|pages|buckets|stats)$/.test(url.pathname),
  new NetworkFirst({
    cacheName: "archive-api-v1",
    networkTimeoutSeconds: 3,
    plugins: [new ExpirationPlugin({ maxEntries: 200 })],
  }),
);
```

Prévoir une politique de quota et une invalidation par version de corpus. Pour un mode hors ligne cohérent, proposer le téléchargement d'un snapshot complet plutôt que mélanger plusieurs générations mises en cache.

Les WebSockets ne sont pas prioritaires : polling conditionnel ou SSE suffisent pour annoncer une nouvelle version et suivre une ingestion unidirectionnelle.

## Vérifications et limites

| Vérification exécutée | Résultat |
|---|---|
| Syntaxe `app.js` | Valide |
| Corpus local chargé | 3 175 pages |
| Chunking KIM sur corpus local | 843 chunks, aucun dépassement de 2 500 caractères |
| Longue réplique synthétique | Dépassement et duplication confirmés |
| Graphe synthétique | Arête terminale et contournement des choix confirmés |
| Canon et template imbriqué | Défauts confirmés |
| LZMA tronqué | Asset incomplet accepté |
| Suggestion `hunhow`, mesure ponctuelle | Environ 101 ms ; pas un benchmark p95 |

Aucune connexion PostgreSQL, vérification externe des endpoints DE, reconstruction de wheel ou validation navigateur multi-appareils n'a été effectuée. Les performances SQL et certains effets UX restent donc à confirmer par tests d'intégration.

Deux décisions produit restent ouvertes : l'application doit-elle rester locale ou devenir multi-utilisateur, et faut-il conserver les pages retirées comme historique ? La licence mérite également clarification : `LICENSE` indique MIT, tandis que `pyproject.toml` déclare `Proprietary`.

## Conclusion

Le projet possède un découpage modulaire exploitable, mais le standard visé se démontrera surtout par des invariants testés, une provenance conservée et une reprise fiable. Corriger d'abord **canon, sémantique KIM et synchronisation**, puis brancher un RAG mesurable, avant d'investir dans une infrastructure plus complexe.
