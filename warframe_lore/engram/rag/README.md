# RAG Architecture & Execution Flow — Cephalon Archive

> **Cognitive Map & Execution Trace**: This document maps the exact end-to-end
> execution pipeline of the RAG subsystem. Use it to trace requests from client
> ingestion to response verification without having to read across all 15 micro-modules.

---

## 1. End-to-End Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor Client
    participant API as api/routers/document_rag.py
    participant Service as rag/service.py
    participant Pipe as rag/pipeline.py
    participant Query as rag/query/ (probes, aliases)
    participant Embed as llm/ (EmbeddingProvider)
    participant DB as rag/retrieval/ (pgvector + dossier)
    participant Rel as rag/retrieval/relevance.py
    participant Prompt as rag/prompt/builder.py
    participant LLM as llm/ (LM Studio)
    participant Verify as rag/verify.py

    Client->>API: POST /v1/rag {question, stream?}
    API->>Service: retrieve(question, context)
    Service->>Pipe: run(question, context, subject?, offset?, exclude_ids?)

    rect rgb(240, 248, 255)
        note over Pipe,Query: Phase 1: Security, Sanitization & Aliases
        Pipe->>Query: sanitize_query(question) [query_guard.py]
        Pipe->>Query: detect_probe(question) [probes.py]
        alt Hostile Probe (SQLi / Jailbreak)
            Pipe-->>Service: Retrieval(prompt.rejected=True, bypass=True)
            Service-->>Client: JAILBREAK_REJECT (No LLM call)
        end
        Pipe->>Query: AliasResolver.resolve(question) [aliases.py]
        Pipe->>Query: search_query(expanded, context) [search_query.py]
    end

    rect rgb(255, 250, 240)
        note over Pipe,DB: Phase 2: Embedding & Dual-Route Retrieval
        Pipe->>Embed: embed([search_query]) -> vector(1024d) [bge-m3]
        Pipe->>DB: router.retrieve(question, vector, story) [routes/router.py]
        alt Factual (Codex)
            DB->>DB: semantic + FTS union, reranked top 10 [routes/codex.py]
        else Narration (Story)
            DB->>DB: pure vector targeting, SQL message_order ASC [routes/story.py]
        end
        opt Targeted Story (subject specified)
            Pipe->>DB: retriever.dossier(subject, vector, exclude_ids) [dossier.py]
        end
    end

    rect rgb(240, 255, 240)
        note over Pipe,Rel: Phase 3: Relevance Filtering & Anti-Hallucination Guards
        Pipe->>Rel: keep_relevant(found, floor) [relevance.py]
        opt No relevant passages
            Pipe->>DB: suggest_title(question) [suggestion.py]
        end
        Pipe->>Rel: missing_entity(question, kept) [relevance.py]
        alt Missing Named Entity (e.g. "Qui est Vena ?")
            note over Pipe,Rel: Anti-hallucination short-circuit
            Pipe-->>Service: Retrieval(hits=[], bypass=True)
        end
    end

    rect rgb(255, 240, 245)
        note over Pipe,Prompt: Phase 4: Prompt Assembly & Auditing
        Pipe->>Prompt: PromptBuilder.build(question, kept, alias_note, suggestion)
        Pipe->>Pipe: audit_retrieval(...) [audit.py]
        Pipe-->>Service: Retrieval(hits, prompt, bypass)
    end

    alt Short-Circuit Active (bypass=True)
        Service-->>Client: RAG_ERROR / Suggestion (No LLM call, 0 tokens)
    else Normal Retrieval (bypass=False)
        rect rgb(245, 245, 255)
            note over Service,Verify: Phase 5: Generation & Post-Verification
            Service->>LLM: chat_stream(prompt.to_messages(), temp=0.1)
            Service->>Verify: verify_answer_with_archive(answer, context) [verify.py]
            Service->>Service: strip_trailing_padding(answer) [sanitize.py]
            Service-->>Client: 200 OK {answer, sources}
        end
    end
```

---

## 2. The 5 Pipeline Phases

| Phase | Responsibility | Key Module / Function | Invariant / Business Rule |
|---|---|---|---|
| **1. Query Sanitization & Expansion** | Normalizes user input, screens out attacks and expands nicknames. | `query/query_guard.py`<br>`query/probes.py`<br>`query/aliases.py`<br>`query/search_query.py` | • Strips non-printable ASCII/control chars.<br>• Hostile probes (SQLi, roleplay overrides) are flagged immediately.<br>• `AliasResolver` maps colloquial names (*"Mercenaire d'Os"*) to canonical names (*"Ordan Karris Ordis"*) **before** embedding.<br>• Resolves anaphoric references using session `RAGContext`. |
| **2. Embedding & Dual-Route Retrieval** | Converts text to dense vectors and dispatches to the Codex or Story strategy. | `llm/lmstudio.py`<br>`retrieval/routes/`<br>`retrieval/hybrid.py`<br>`retrieval/dossier.py` | • 1024-dimensional embeddings via local `bge-m3`.<br>• **Codex**: semantic (`MergedRetriever`) + full-text (`HybridSearch.lexical_hits`) union, reranked to the 10 most relevant passages.<br>• **Story**: pure vector targeting, NO lexical channel and NO reranker; SQL imposes `message_order ASC NULLS LAST` and excludes `game_updates` / `game_announcements` / `patch_notes`.<br>• Cosine distance (`<=>`) backed by HNSW index (`ef_search = 200`).<br>• In story mode (`subject`), queries biographical pages first (`dossier.py`, order preserved). |
| **3. Relevance & Anti-Hallucination** | Filters noise and prevents hallucinations on absent entities. | `retrieval/relevance.py`<br>`retrieval/suggestion.py` | • **Relevance floor**: passages with cosine score < `0.50` are dropped.<br>• **Entity guard**: for *"Qui est X ?"*, if "X" is absent from all retained chunks, short-circuit immediately.<br>• If weak match: suggests close canon title (*"Voulez-vous dire « Y » ?"*). |
| **4. Strict Prompt Assembly** | Delimits context inside XML tags with amnesia directives. | `prompt/builder.py`<br>`prompt/guards.py`<br>`audit.py` | • Single system message with `<archives>{context}</archives>`.<br>• Real-world amnesia directive (prevents leaking pre-trained world knowledge).<br>• Context capped at `max_context_chars` (default ~4500-6000 chars / ~1500 tokens).<br>• Audit line logged via `audit_retrieval()`. |
| **5. Inference & Verification** | Generates response and verifies groundedness. | `service.py`<br>`verify.py`<br>`sanitize.py` | • **Low temperature (`0.1`)** for deterministic factual generation.<br>• Post-generation check (`verify_answer_with_archive`): checks if key entities in the answer exist in the context.<br>• Strips trailing padding/formatting noise. |

---

## 3. The 3 Short-Circuit Mechanisms (Zero-LLM Abstention)

The model is intentionally **never called** when any of the following conditions occur:

1. **Hostile Probe (`rejected=True`)**:
   - Query matches SQL injection signatures, prompt injection attempts, or roleplay hijack patterns (`detect_probe`).
   - Served immediately with `JAILBREAK_REJECT`. Costs zero GPU compute and doesn't pollute session memory.
2. **Relevance Floor Drop (`hits == [] and suggestion is None`)**:
   - Out-of-corpus topics, random chatter, or typos with similarity below the critical floor (calibrated at `0.50`).
   - Served with standard mnemonic `RAG_ERROR` (*"Données insuffisantes ou inexistantes dans les archives..."*).
3. **Missing Named Entity (`missing_entity != None`)**:
   - Query asks for a specific subject (*"Qui est Vena ?"*), but the retrieved chunks do not contain that name.
   - Prevents the LLM from hallucinating a plausible fiction when the corpus is silent.

---

## 4. Narrative Mode (Pagination & Continuation)

Targeted stories (*"Raconte-moi l'histoire de Lettie"*) use a dedicated continuation protocol:
- **Route selection**: `RetrievalRouter` sends narration wording (or the explicit `story` flag) to `StoryRoute`; factual lookups go to `CodexRoute`.
- **Chronology**: `StoryRoute` only picks the semantic neighbourhood — the final order is SQL's (`coalesce(kim_dialogue.message_order, game_dialogue.message_order) ASC NULLS LAST`, then page and chunk id), never the vector's.
- **`subject`**: Reads the subject's own wiki page chunks in narrative order first (tier SQL).
- **`exclude_ids`**: The **only** cursor mechanism. Chunks already shown are recorded and excluded in subsequent turns (`NOT (lore_chunks.id = ANY(:exclude_ids))`).
- **`offset > 0`**: Continuation turns omit semantic neighbours to prevent re-anchoring on the same introductory facts.

