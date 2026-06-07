# src/rag — RAG Pipeline

Retrieval-Augmented Generation pipeline over the `docs/` product documentation. Provides the knowledge base the orchestrator uses to answer customer questions.

---

## Files

### `ingestion.py`
Loads and chunks all 10 markdown files from `docs/`.

**Two-stage chunking:**
1. `MarkdownHeaderTextSplitter` — splits at `#`, `##`, `###` headings. Each section becomes a separate document with the heading stored in metadata
2. `RecursiveCharacterTextSplitter` — further splits any section exceeding 500 characters (100 char overlap)

**Result:** 109 chunks from 10 documents.

**Metadata per chunk:**
```python
{
  "source_file": "sso-setup-v3.md",
  "category": "authentication",
  "version": "3.x",
  "section": "Prerequisites",
  "is_adversarial": False,
}
```

**`DOC_METADATA` map** — hardcoded mapping of filename → (category, version, is_adversarial). This is the source of truth for what each document covers.

---

### `embeddings.py`
Singleton embedding model using `sentence-transformers/all-MiniLM-L6-v2`.

- **384 dimensions** — compact and fast
- **Semantic similarity** — "CSV export failing" matches "row limit exceeded" even with no shared words
- **Normalized embeddings** — cosine similarity works directly
- **Runs locally** — no API cost, no network dependency
- Loads once on first import, cached in `~/.cache/huggingface/`

---

### `vector_store.py`
ChromaDB interface. Persists embeddings to `.chroma_store/` on disk.

Key functions:
- `get_vector_store()` — singleton, connects to existing collection or creates new
- `add_chunks(chunks)` — embeds and stores document chunks (converts `is_adversarial` bool → int for ChromaDB compatibility)
- `similarity_search_with_score(query, k, filter)` — dense semantic search returning (document, score) tuples
- `get_collection_count()` — returns total stored chunks

**ChromaDB limitation:** metadata values must be `str`, `int`, or `float`. No nested dicts or lists. `is_adversarial` stored as `0` or `1`.

---

### `retriever.py`
Hybrid retrieval combining dense (ChromaDB) and sparse (BM25) search.

**`build_bm25_index(chunks)`** — builds in-memory BM25 index from all chunks. Called once at startup, rebuilds in milliseconds. Does not persist to disk.

**`_build_metadata_filter(version, category, exclude_adversarial)`** — builds ChromaDB `$where` filter:
```python
# Example for version="3.2", exclude_adversarial=True
{
  "$and": [
    {"is_adversarial": {"$eq": 0}},          # blocked at DB level
    {"$or": [
      {"version": {"$eq": "3.2"}},
      {"version": {"$eq": "3.x"}},
      {"version": {"$eq": "all"}},
    ]}
  ]
}
```

**`hybrid_search(query, version, category, exclude_adversarial)`** — main retrieval function:
1. Dense search → top 5 from ChromaDB with metadata filter
2. Sparse search → top 5 from BM25 (no filter — keyword matching)
3. Merge: if chunk appears in both → `combined = 0.6 × dense + 0.4 × sparse`
4. If dense only → `combined = dense_score`
5. If sparse only → `combined = 0.4 × sparse_score`
6. Filter adversarial results
7. Sort by combined score, return top 3

---

### `reranker.py`
Cross-encoder reranking using `cross-encoder/ms-marco-MiniLM-L-6-v2`.

**Why cross-encoder?** Unlike bi-encoders (embeddings), cross-encoder reads query + document together as a pair and scores relevance directly. More accurate but slower — only applied to the small top-k set, not all 109 chunks.

**Scores:** Raw logits, not 0-1. Higher = more relevant. Typical range: -15 to +15.

**Fallback:** If cross-encoder fails to load, uses `combined_score` as `rerank_score`. No crash.

**`rerank(query, results, top_k)`:**
```
input: top-k results from hybrid_search
       ↓
cross-encoder scores each (query, chunk) pair
       ↓
re-sort by rerank_score
       ↓
return top_k reranked results
```

---

### `guard.py`
Two types of content detection:

**`contains_injection(text)`** — regex patterns for prompt injection:
- `ignore all previous instructions`
- `system override`
- `you are now a different AI`
- `bypass all filters`
- etc.

**`is_unauthorized_request(query)`** — regex patterns for cross-tenant data access:
- `show me all customers`
- `list all enterprise customer details`
- `reveal other tenant data`
- etc.

**`inspect_query(query)`** — full query assessment:
```python
{
  "safe": True/False,
  "injection_detected": True/False,
  "unauthorized_access": True/False,
  "threat_level": "none" / "medium" / "high"
}
```

**`filter_results(results)`** — removes adversarial chunks from RAG results (second line of defense after DB-level filter).

**`is_adversarial_source(source_file)`** — checks against `settings.blocked_sources_list` (default: `["system-override.md"]`).

**Input length guard:** Queries over 1000 characters are flagged as potential ReDoS attacks before regex patterns run.
