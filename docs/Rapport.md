# Technical Audit Report: Cephalon Archive

**The top priority is data fidelity, ahead of vector optimization or containerization.** Several current behaviors can retain obsolete archives, classify speculation as canon, or produce an incorrect KIM flow.

Audit of commit `28baaab`, local branch `dev`, with no project modifications during the audit. The examples below are proposed corrections, not applied changes.

## Priority Findings

`P1`: must be fixed before considering the corpus reliable for RAG. `P2`: robustness, security or UX to address before wider distribution. No compromise incident was observed.

### 1. P1: SQL/JSON Synchronization Can Diverge

References: [scraper.py:173](warframe_lore/scraper.py#L173), [scraper.py:281](warframe_lore/scraper.py#L281), [writer.py:55](warframe_lore/output/writer.py#L55), [manager.py:295](warframe_lore/db/manager.py#L295).

The current processing follows this order:

```text
SQL Write → SQL Delta Validation → JSON Bucket Publication
```

If JSON publication fails, the next run nevertheless considers the page as synchronized. The JSON can remain stale indefinitely.

Two related issues exist:

- JSON merge is additive: a page removed from a bucket remains in its old megafile.
- `purge_vanished_pages()` deletes the synchronization state, not the SQL page or its derivatives.

**Minimal fix:** acknowledge synchronization only after successful publication, and reconcile assignments with a complete inventory.

**Preferable architecture:** PostgreSQL becomes the single source of truth; megafiles become a regenerable projection, independent of network delta.

```python
# Pseudocode: proposed contracts, currently absent.
async with repository.transaction() as tx:
    await tx.upsert_page(page)
    await tx.record_revision(page)
    await tx.mark_bucket_dirty(bucket_id)

# Executed also when no page requires downloading.
for bucket_id in await repository.dirty_buckets():
    snapshot = await repository.bucket_snapshot(bucket_id)
    publisher.publish_atomically(snapshot)
    await repository.mark_published(bucket_id, snapshot.revision)
```

The final marking must be conditioned on the published revision: a concurrent modification must not be acknowledged by mistake.

For disappearances, explicitly choose between deleting the current corpus and historical retention with `retired_at`. Never infer a deletion from a partial or failed category resolution.

### 2. P1: Canon Ranking Contradicts Its Contract

References: [output/models.py:34](warframe_lore/output/models.py#L34), [scraper.py:106](warframe_lore/scraper.py#L106), [cleaner/pipeline.py:199](warframe_lore/cleaner/pipeline.py#L199).

Three defects are identified:

- Priorities increase with uncertainty, but `merge_canon_status()` uses `min()`.
- The simultaneous presence of canon and speculative signals results in `canon`.
- Nested speculative templates are not detected by the first-level traversal.

Reproduced result:

```python
merge_canon_status(CanonStatus.CANON, CanonStatus.SPECULATION)
# Current: CanonStatus.CANON
```

Targeted corrections:

```python
# output/models.py: keep the existing empty-case handling.
return max(present, key=lambda status: _CANON_PRIORITY[status])

# scraper.py
if page_level_speculative or inline_non_canon:
    return CanonStatus.SPECULATION
return CanonStatus.CANON

# pipeline.py: detect before replacing/flattening templates.
non_canon_detected = any(
    must_flag_non_canon(node, self.cleaner_config)
    for node in parsed.filter_templates(recursive=True)
)
```

Long-term, a page can contain multiple reliability levels. Retaining a cautious page-level status with a precise provenance per section/chunk will avoid discarding an entire article for a single speculative passage.

### 3. P1: KIM Graph Loses Its Semantics

References: [cleaner/pipeline.py:144](warframe_lore/cleaner/pipeline.py#L144), [chunker.py:43](warframe_lore/db/chunker.py#L43), [server.py:747](warframe_lore/ui/server.py#L747), [app.js:775](warframe_lore/ui/static/app.js#L775).

The `{If ...}` conditions, `{P1}` markers and some redirects are deleted **before storage**. What was meant to be hidden in RP mode also disappears from the representation usable by RAG.

The reconstructed graph also contains verified errors:

- A terminal choice receives an edge to the next line.
- A direct NPC → NPC edge allows bypassing choices.
- The simulator ignores `option.ends`.
- A step with `jump_to` is skipped before displaying its own line.

**Architectural fix: parse once, produce multiple views.**

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

The RP view displays `text`. The simulator and RAG also use `conditions` and `next_ids`. Unresolved destinations must be flagged, not silently replaced by a sequential flow.

Invariants to enforce:

```python
assert all(edge["target"] in nodes_by_id for edge in edges)
assert not any(
    nodes_by_id[edge["source"]].terminal
    for edge in edges
)
```

Immediate fix for the terminal choice:

```javascript
appendSimBubble({ ...option, speaker: "", player: true });
if (option.ends) {
  simEnd();
  return;
}
kimSimState.cursor++;
simNext();
```

This is not enough to reconstruct the lost branches. Pages already cleaned will need to be reprocessed from a source that retains their annotations.

### 4. P1: Dialogue Chunking Does Not Always Respect Its Bounds

Reference: [chunker.py:218–256](warframe_lore/db/chunker.py#L218).

A synthetic line of 6,012 characters produces:

```text
[2500, 2500, 1512, 6012]
```

It is split, then re-emitted in full. Placed after a short line, it bypasses the fallback and remains whole.

**Nuance:** this defect was not triggered by the 843 KIM chunks recalculated on the local corpus; their observed maximum is 2,499 characters.

Processing long lines before the ordinary overflow fixes both paths:

```python
# Place before the ordinary line treatment.
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

Other limitations of dialogue mode: it bypasses the headings pass and does not apply textual overlap between ordinary chunks. Speakers, however, accumulate even when they no longer appear in the emitted text.

The lasting fix is to split first by conversation/section, then by turns of speech, with overlap of actually retained turns.

### 5. P1: A Regex Has High Polynomial Cost

References: [cleaner/pipeline.py:88](warframe_lore/cleaner/pipeline.py#L88), with variants in `chunker.py`, `server.py` and `app.js`.

The following prefix allows multiple concurrent distributions of the same spaces:

```regex
^>\s*\*{0,3}\s*>?\s*
```

On the input `">" + " " * n + "X"`, complete cleaning took approximately:

| Spaces | Time |
|---:|---:|
| 100 | 0.006 s |
| 200 | 0.035 s |
| 400 | 0.275 s |

The growth is consistent with cubic cost. This is a credible blocking risk on adversarial wiki content, **not a confirmed observed attack**.

Replace the ambiguous prefix with:

```python
prefix = (
    r"(?im)^>[ \t]*"
    r"(?:\*{1,3}[ \t]*)?"
    r"(?:>[ \t]*)?"
)
```

The optional spaces then follow an effectively consumed marker. Add tests for the four variants and input size budgets.

More generally, use the AST for nested structures and reserve regexes for local transformations. For example, the current order removes HTML tags before deleting certain code blocks; their content persists. Immediate fix:

```python
text = strip_wikitext_comments(wikitext)
text = strip_tables_and_code_blocks(text)
text = convert_html_tags(text)
```

### 6. P1: Public Export Is Not Verified as Claimed

References: [export.py:37](warframe_lore/export.py#L37), [export.py:64](warframe_lore/export.py#L64), [export.py:159](warframe_lore/export.py#L159).

The separation of responsibilities is correct:

```text
Origin HTTPS → compressed index
Content      → manifests designated by the index
```

However:

- Manifests are downloaded over **HTTP**.
- The hash suffix serves as a cache key; no verification of bytes against this digest is performed.
- An existing cache is accepted without validation and written directly before parsing.
- A truncated LZMA index can produce an incomplete name accepted as an asset.

Reproduced example after truncation of a synthetic stream:

```text
ExportWeapons_en.json!00_
```

**The content-addressed name alone is not proof of integrity.**

Download contract fix:

```python
# Pseudocode: mandatory validation before cache publication.
payload = fetch_authenticated(asset_url)
document = json.loads(payload.decode("utf-8"))

if not isinstance(document, dict):
    raise ValueError("Invalid manifest")
if not isinstance(document.get(category), list):
    raise ValueError("Missing or invalid category")

verify_provider_digest(payload, expected_digest)
atomic_cache_write(cache_path, payload)
```

`verify_provider_digest()` requires documenting the actual algorithm of the provider; SHA-256 must not be assumed arbitrarily. HTTPS support of the Content endpoint must also be verified before modification, which was not done during this audit.

For LZMA, a strict bounded policy would be:

```python
limit = 2 * 1024 * 1024  # Index budget to calibrate.
decoder = lzma.LZMADecompressor(
    format=lzma.FORMAT_ALONE,
    memlimit=64 * 1024 * 1024,
)
decoded = decoder.decompress(raw, max_length=limit + 1)
if len(decoded) > limit or not decoder.eof:
    raise ValueError("Index too large or incomplete")
```

If the absence of EOF is a confirmed provider-specific behavior, provide an explicit exception with validation of complete lines and expected categories, rather than indiscriminately accepting any decoded prefix.

### 7. P1: RAG Persistence Is Incomplete and Destructive

References: [models.py:96](warframe_lore/db/models.py#L96), [manager.py:158](warframe_lore/db/manager.py#L158), [init_db.sql:72](init_db.sql#L72).

**Functional gap:** `embedding vector(384)` exists, but the audited pipeline neither computes nor inserts vectors. No vector search is wired to the interface.

**Lifecycle defect:** every upsert deletes and recreates chunks. Any externally added embedding would be lost, even for unchanged text.

Preserve enrichments only when their entry remains identical:

```sql
-- Fragment of chunk upsert.
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

Then delete orphaned indices. Long-term, compare the fingerprint of the actually encoded text with the model version, rather than all metadata.

**ORM/DDL Divergence:** the SQL declares GIN, HNSW and title uniqueness; the models do not reproduce them. This is not proof that the deployed database lacks indexes, but two initialization modes can produce two different schemas.

```python
Index("idx_wiki_pages_title", WikiPage.page_title, unique=True)
Index("idx_chunks_metadata", LoreChunk.__table__.c.metadata,
      postgresql_using="gin")
Index("idx_chunks_embedding", LoreChunk.embedding,
      postgresql_using="hnsw",
      postgresql_ops={"embedding": "vector_cosine_ops"})
```

A versioned migrations procedure must become the reference, with model consistency testing.

### 8. P2: Frontend Bootstrap Reinstalls Events

References: [app.js:1110](warframe_lore/ui/static/app.js#L1110), [app.js:1178](warframe_lore/ui/static/app.js#L1178), [app.js:554](warframe_lore/ui/static/app.js#L554).

The Reload button calls `init()`, which adds new anonymous listeners to persistent elements. After a reload, the burger can perform two successive invocations and appear to stop working.

Minimal fix:

```javascript
$("#btn-reload").addEventListener("click", () => {
  window.location.reload();
});
```

For a refresh without navigation, separate one-time event installation from data reloading.

Asynchronous renders also present a race condition: opening A then B can leave a late response from A overwriting B's content.

```javascript
let routeEpoch = 0;

function handleRoute() {
  const epoch = ++routeEpoch;
  // Pass epoch to the route-chosen render.
}

async function renderPage(bucketId, title, epoch) {
  const page = await api(
    `/api/page?bucket=${encodeURIComponent(bucketId)}&title=${encodeURIComponent(title)}`
  );
  if (epoch !== routeEpoch) return;
  // Apply render only after this guard.
}
```

Apply the same principle to errors, suggestions and tab changes, with optional cancellation via `AbortController`. A Vue migration would not automatically remove these races.

### 9. P2: Cache Guarantees Neither Consistency Nor Freshness

References: [server.py:103](warframe_lore/ui/server.py#L103), [app.js:62](warframe_lore/ui/static/app.js#L62).

The server reloads all files at expiry without a lock and publishes `_buckets` then `_pages` separately. Concurrent requests may work on different generations.

Conversely, the browser retains responses in a `Map` without expiration: `Cache-Control: no-store` does not purge this application cache.

Recommended server contract:

```python
# Pseudocode: readers capture a single reference.
with self._reload_lock:
    if time.monotonic() < self._next_reload:
        return
    snapshot = self._read_validated_snapshot()
    self._snapshot = snapshot
    self._next_reload = time.monotonic() + 5
```

Retain the last valid snapshot on failure. To guarantee consistency across multiple megafiles, publish a complete generation then switch a reference manifest.

Minimal client fix:

```javascript
const hit = apiCache.get(path);
if (cache && hit && hit.expiresAt > performance.now()) {
  return hit.data;
}

// After receipt:
apiCache.set(path, {
  data,
  expiresAt: performance.now() + 5000,
});
```

`state.stats`, buckets and KIM caches must also be invalidated. A shared corpus version is more reliable than an accumulation of independent TTLs.

### 10. P2: HTTP/HTML Boundaries Need Hardening

References: [server.py:833](warframe_lore/ui/server.py#L833), [server.py:918](warframe_lore/ui/server.py#L918), [app.js:115](warframe_lore/ui/static/app.js#L115).

The server listens only on `127.0.0.1`, which greatly reduces current exposure. Nevertheless:

- `limit=-1` is accepted and returns nearly all results.
- Threads and search cost are not capped.
- `Access-Control-Allow-Origin: *` allows cross-origin reads when the browser permits access to the local service.
- Markdown rendering does not filter link protocols.

First safeguards:

```python
limit = max(1, min(_int_from_query(query, "limit", 50), 200))
if len(query_text) > 256:
    self.send_error(400, "Query too long")
    return
```

For the current local launch, check `Host`/`Origin` before processing and remove the CORS wildcard. A deployment configuration must explicitly define its authorized origins.

For links, use a Markdown parser with controlled rendering; failing that, build links from validated tokens:

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

No XSS execution has been demonstrated. No exploitable traversal has been confirmed: static routes are fixed and media goes through a generated name list.

### 11. P2: Search, Accessibility and Spoilers Remain Incomplete

References: [app.js:1034](warframe_lore/ui/static/app.js#L1034), [app.js:1230](warframe_lore/ui/static/app.js#L1230), [styles.css:879](warframe_lore/ui/static/styles.css#L879), [app.js:547](warframe_lore/ui/static/app.js#L547).

**Search:** after suggestions appear, Enter does nothing if no suggestion is selected, because the index is `-1`.

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

**Accessibility:** results and cards are clickable `div`s. Use native links:

```javascript
const item = el("a", "page-list-item");
item.href = `#page?${encodeURIComponent(bucketId)}?${encodeURIComponent(title)}`;
```

On mobile, make the closed sidebar `inert`, handle Escape and restore focus to the burger. The tablet rail currently hides bucket labels; removing this incomplete rail is preferable to empty buttons.

**Spoilers:** the code shows a warning but immediately inserts the content. An accessible first block can be native:

```javascript
function spoilerBlock(body, reason) {
  const box = el("details", "spoiler-block");
  box.append(el("summary", null, `Show spoiler: ${reason}`), body);
  return box;
}
```

Apply the same policy to snippets, the simulator and graph assembly. This is a UX control, not a security barrier.

## Actual Stack

Several items in the context describe a target rather than the present implementation.

| Announced Element | Observed State |
|---|---|
| Vue Composition API Frontend | Main application in native JavaScript; Vue used for the flowchart |
| Tailwind CSS | Custom CSS, no versioned Tailwind chain |
| `MarkdownHeaderTextSplitter` / `RecursiveCharacterTextSplitter` | Native equivalents, no LangChain |
| PostgreSQL + pgvector | Schema present; embedding production and retrieval not wired |
| JSONB Dialogue Graph | JSONB for chunk metadata; relational KIM messages; graph reconstructed in memory |
| Public Export Hash Verification | Cache by hashed name, no cryptographic content verification |
| Dynamic `<SpoilerBlock>` | Warning, no operational masking component |
| Docker | Documented command for PostgreSQL; no versioned Dockerfile/Compose |

Using native JavaScript or a custom splitter is not the problem. The problem is the gap between claimed guarantees and those actually tested.

## Architecture and Flow

The foundations to keep are sound: separate modules, explicit data models, per-page SQL transactions, atomic JSON file replacement, and i18n identity `(entity_id, lang)`.

The reasonable target remains a **modular monolith**, not a premature set of microservices:

```text
MediaWiki / Public Export
          |
          v
Versioned raw sources + provenance
          |
          v
Structural parsing: lore / dialogue / entity
          |
          v
PostgreSQL: current state + useful history
          |
          +--> Chunks --> embeddings --> retrieval
          +--> Validated graph --> simulator / Flow View
          +--> Versioned megafiles --> local reading
```

**Useful SOLID, without over-architecture:**

- **SRP:** the parser produces a business structure; the renderer decides what is visible.
- **DRY:** a single KIM parser must feed SQL, graph, simulator and RAG.
- **DIP:** inject source, cleaner and repository instead of building them mandatorily in `Scraper`.
- **KISS:** keep PostgreSQL and a simple worker; Redis, Kafka or a graph database are not yet justified.

Example of minimal injection, reusing `BaseSource`:

```python
def __init__(self, config, *, source=None, cleaner=None):
    self.config = config
    self.source = source if source is not None else MediaWikiSource(config)
    self.cleaner = cleaner if cleaner is not None else WikitextCleaner()
```

**Identifiable bottlenecks:**

The delta rereads the complete state of a bucket for each page: for a bucket of `N` pages, this means `N` queries and potentially `N²` transferred records. Loading the state once is sufficient:

```python
states = {
    spec.id: await self.db.fetch_sync_state(spec.id)
    for spec in self.buckets.specs
}
stored = states[bucket_id].get(page_title)
fresh = stored is not None and stored["touched"] == touched
```

GIN and HNSW exist in the DDL. Their coexistence does not guarantee filtering before ANN. For example, prefer an expression compatible with the existing GIN:

```sql
WHERE metadata @> '{"speakers":["Amir"]}'::jsonb
```

No PostgreSQL bottleneck was measured: execution plans and filter recall on a test database will need to be examined. JSONB is not inherently problematic; a large full graph rewritten on every modification could become one. Relational nodes/edges with JSONB conditions constitute a possible evolution, not an immediate necessity.

## RAG Optimization

The priority is not simply to increase chunks. It is to retrieve **consistent, typed evidence**.

| Content | Recommended Unit | Context to Retrieve |
|---|---|---|
| Lore | Section then chunks under tokenizer budget | Title, hierarchy, parent section |
| Dialogue | Turns of speech from a compatible branch | Conversation, conditions, preceding choice, relevant neighbors |
| Statistics | Structured entity data | Official ID, game/export version, units |

Numerical statistics are currently excluded by the i18n extraction, which retains mainly name and description: [export.py:210](warframe_lore/export.py#L210). Do not expect the model to reconstruct missing values.

A simple extension would preserve technical data separately:

```sql
CREATE TABLE game_entity_snapshot (
    entity_id   TEXT NOT NULL,
    export_hash TEXT NOT NULL,
    stats       JSONB NOT NULL,
    PRIMARY KEY (entity_id, export_hash)
);
```

**FR/EN: join on the official ID, never on a translated name.**

```sql
SELECT en.entity_id, en.name AS name_en, fr.name AS name_fr
FROM game_entities_i18n en
LEFT JOIN game_entities_i18n fr
  ON fr.entity_id = en.entity_id AND fr.lang = 'fr'
WHERE en.lang = 'en';
```

Then explicitly associate wiki pages and entities. Simplified display titles must not become identifiers.

**Recommended retrieval:**

1. Resolve language, entities, question type and canon/spoiler policy.
2. Combine lexical and vector matches.
3. Merge ranks, then optionally rerank.
4. Extend results to the parent section or compatible branch neighbors.
5. Produce a cited response, with abstention if evidence is missing.

Minimal vector query, once embeddings are populated:

```sql
SELECT c.id, c.content_markdown, c.metadata, p.source_url
FROM lore_chunks c
JOIN wiki_pages p ON p.page_id = c.wiki_page_id
WHERE c.embedding IS NOT NULL
  AND p.canon_status = :canon_status
ORDER BY c.embedding <=> CAST(:query_vector AS vector(384))
LIMIT :k;
```

The chosen model must actually produce 384 dimensions. Version the model, tokenizer, encoded input and pipeline; do not mix their vector spaces.

An RRF merge avoids directly comparing incompatible scores:

```python
from collections import defaultdict

scores = defaultdict(float)
for ranking in (lexical_ids, vector_ids):
    for rank, chunk_id in enumerate(ranking, start=1):
        scores[chunk_id] += 1 / (60 + rank)

selected = sorted(scores, key=scores.get, reverse=True)[:20]
```

For KIM, do not expand all possible paths: use local windows compatible with conditions, otherwise the number of traversals can explode.

## Major Improvements

I recommend four investments, in this order.

### 1. Replayable Ingestion

Retain raw sources and identify each derivation by revision and pipeline version. Replayable publication from finding 1 allows repairing a projection without re-downloading the wiki.

```python
derivation_key = (
    source_id,
    source_revision,
    cleaner_version,
    chunker_version,
    embedding_model_version,
)
```

Tracking must distinguish downloaded, validated, parsed, indexed and published. Add failure counters, durations and explicit partial state.

### 2. Testing and Evaluation

No test suite or versioned CI was found. Start with the invariants that protect data:

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

Complete with JSON failure recovery tests, terminal branches, inverted network responses and keyboard navigation. For RAG: FR/EN question set, Recall@k, citation fidelity, cross-branch contradictions and p95 latency.

### 3. Reproducible Deliveries

Version locked dependencies, Vue Flow bundle recipe, migrations and test Compose. The current bundle is delivered without a versioned rebuild recipe.

Another distribution defect is visible: `cleaner_config.json` and `init_db.sql` are looked up outside the package. After moving to embedded resources:

```python
from importlib.resources import files

root = files("warframe_lore").joinpath("resources")
cleaner_json = root.joinpath("cleaner_config.json").read_text(encoding="utf-8")
schema_sql = root.joinpath("init_db.sql").read_text(encoding="utf-8")
```

Test a wheel outside checkout. For Docker: non-root user, persistent volumes, healthchecks, external secrets and a pinned PostgreSQL/pgvector image. Network exposure will also require replacing or hardening the current local HTTP server.

### 4. Offline Reading

A PWA is relevant for an archive. It must distinguish application resources, versioned data and images.

Example Workbox strategy, a library to introduce explicitly:

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

Provide a quota policy and invalidation by corpus version. For a consistent offline mode, offer downloading a complete snapshot rather than mixing multiple cached generations.

WebSockets are not a priority: conditional polling or SSE are sufficient to announce a new version and track unidirectional ingestion.

## Verifications and Limitations

| Verification Performed | Result |
|---|---|
| `app.js` syntax | Valid |
| Local corpus loaded | 3,175 pages |
| KIM chunking on local corpus | 843 chunks, no 2,500-character overflow |
| Long synthetic line | Overflow and duplication confirmed |
| Synthetic graph | Terminal edge and choice bypass confirmed |
| Canon and nested template | Defects confirmed |
| Truncated LZMA | Incomplete asset accepted |
| `hunhow` suggestion, spot measurement | Approximately 101 ms; not a p95 benchmark |

No PostgreSQL connection, external DE endpoint verification, wheel rebuild or multi-device browser validation was performed. SQL performance and certain UX effects therefore remain to be confirmed by integration tests.

Two product decisions remain open: should the application remain local or become multi-user, and should retired pages be kept as history? The license also merits clarification: `LICENSE` states MIT, while `pyproject.toml` declares `Proprietary`.

## Conclusion

The project has a usable modular decomposition, but the target standard will be demonstrated primarily through tested invariants, preserved provenance and reliable recovery. First fix **canon, KIM semantics and synchronization**, then wire a measurable RAG, before investing in more complex infrastructure.
