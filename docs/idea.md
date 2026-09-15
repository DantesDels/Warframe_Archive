# Roadmap and Vision — "Cephalon Archive" Project

**Goal:** Create the ultimate knowledge base for the Warframe universe,
usable by Language Models (LLMs) and RAG applications
(Retrieval-Augmented Generation).

---

## 1. Modularity: Project Foundations

The project relies on a decoupled architecture (see `docs/architecture.md`).
Each component has a single responsibility, allowing one module to evolve
without breaking the rest of the system.

- **Extraction (`api`):** handles only communication with the MediaWiki API
  (`BaseSource` interface). If the API changes, only this module is affected.
- **Cleaning (`cleaner`):** transforms Wikitext into clean Markdown, with
  filtering of noise, gameplay sections, and canon detection.
- **Synchronization (`sync`):** ensures "Delta" mode (only process new items),
  later relayed to the SQL database.
- **SQL Persistence (`db`):** normalized PostgreSQL (3NF), pgvector embeddings,
  RAG chunking (`ChunkManager`), database-backed delta.
- **Export (`output`):** formats the final data (JSON megafiles per bucket,
  with `canon_status`).
- **Source Extensibility:** the architecture allows easily adding new "Clients"
  (e.g. `RedditScraper` for r/Warframe, `ForumScraper` for official patch
  notes) that plug into the same pipeline.

## 2. Scalability: Industrialization and Scaling

To go beyond the limits of a personal notebook and create a tool usable at
scale, the architecture can evolve toward Cloud and Big Data standards.

- **Robust HTTP Scraping (done):** `requests` + built-in retries/backoff/
  politeness; async database side (SQLAlchemy 2.0 async + asyncpg). A full
  switch to `aiohttp` would allow further parallelization of extraction.
- **Vector Database (started):** the `db` layer now stores each chunk with its
  `vector(384)` embedding (pgvector). The JSON network is no longer alone:
  semantic searches can be performed directly in SQL.
- **CI/CD Pipeline (upcoming):** deployment on GitHub Actions or AWS Lambda
  with a cron trigger; the script runs autonomously (e.g. every Tuesday after
  Warframe updates) and updates the database without human intervention.

## 3. Technical Optimizations (Data Prep)

Data quality for LLMs is a permanent product axis.

- **Smart Chunking (done, Phase 2.5):** `ChunkManager` splits long pages into
  semantic blocks (target 1200c, dialogues 2500c) while respecting headings
  (`##`/`###`) and paragraphs. Two passes: structural (headers in metadata)
  + recursive with overlap, plus a dedicated mode for KIM/RPG/Quest dialogues
  (`speakers` in metadata).
- **Metadata Enrichment (partial):** each chunk carries usable metadata
  (heading hierarchy, speakers) stored as JSONB and filterable via GIN index
  before sending to the LLM. An NLP pass for automatic tagging (e.g.
  `Tags: [Grineer, Clonage, Tyl Regor]`) remains possible.
- **Canon Detection (done):** each entry exposes `canon_status`
  (`canon` / `speculation` / `community_theory`) detected via
  `Category:Speculation` and inline markers; `merge_canon_status` retains the
  most cautious status.
- **Multimedia Management (upcoming):** systematic extraction of image URLs
  (portraits, maps, symbols) so that future interfaces display the character's
  image alongside the text response.

## 4. Current Use Cases (MVP - Minimum Viable Product)

With the JSON database (megafiles) and the SQL layer (pgvector + JSONB) fed
into a NotebookLM-type tool or an RAG pipeline, the following is already
achievable:

- **The Warframe Oracle:** an assistant capable of cross-referencing game
  texts to answer complex questions without "hallucinating" (e.g. "What is
  the chronology of Parvos Granum's rebellion?"), while filtering canon.
- **Virtual Game Master (GM):** using specifically the "Fables & Frontiers"
  RPG data and the KIM system (dedicated dialogue mode, speakers preserved),
  the AI can embody Amir and run original campaigns with the exact rules of
  this universe.
- **Lore Audit:** the AI can analyze the entire text to spot narrative
  inconsistencies or unresolved plot holes left by Digital Extremes over the
  years.

## 5. Future Developments (Long-Term Vision)

Once the data is perfectly structured and vectorized, the project can open up
to third-party applications via frameworks like LangChain or LlamaIndex.

- **Standalone RAG Application and Discord Bot:** development of a Python
  backend connected to a Discord Bot or Web interface (Streamlit/Vue.js).
  Players ask a question on their server, the bot queries the vector database,
  and the AI formulates the answer instantly.
- **Automated Content Generator:** coupling the database with AI voice
  generators (ElevenLabs) and visual generators (Midjourney). The tool could
  script, illustrate, and narrate automated lore analysis videos with each
  new update.
- **Interactive AI Personas:** creation of conversational agents adopting the
  psychological personality and exact vocabulary of a specific character
  (e.g. a "Ballas" chatbot that debates Orokin philosophy using exclusively
  his rhetorical style extracted from the wiki).
