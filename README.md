# Agentic Support System

An agentic AI system that receives customer support queries and attempts to resolve them autonomously. Built for FlowDesk, a fictional SaaS company.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Tech Stack](#tech-stack)
- [Setup Guide](#setup-guide)
- [Running the System](#running-the-system)
- [API Reference](#api-reference)
- [Agent Workflow](#agent-workflow)
- [RAG Pipeline](#rag-pipeline)
- [Security](#security)
- [Test Results](#test-results)
- [Design Decisions](#design-decisions)

---

## Overview

This is **not a chatbot**. It is a multi-step agentic system that:

1. Receives a customer query with a customer ID
2. Classifies the intent using GPT-4o-mini
3. Dynamically selects the minimum required tools
4. Orchestrates multi-step workflows using LangGraph
5. Validates and cross-references results from multiple sources
6. Decides whether to auto-resolve or escalate to human support
7. Returns a structured JSON response with citations, tool trace, and confidence score

---

## Architecture

```
POST /support/query
        │
        ▼
┌───────────────────┐
│   Guard Layer     │  ← Prompt injection + unauthorized access detection
└───────┬───────────┘
        │
        ▼
┌───────────────────┐
│ Intent Classifier │  ← GPT-4o-mini classifies query into 9 intents
└───────┬───────────┘
        │
        ▼
┌───────────────────────────────────────────────────┐
│              LangGraph Orchestrator               │
│                                                   │
│  fetch_customer → [route by intent]               │
│                        │                          │
│         ┌──────────────┼──────────────┐           │
│         ▼              ▼              ▼           │
│    search_kb   check_incidents  run_diagnostics   │
│         │              │              │           │
│         └──────────────┴──────────────┘           │
│                        │                          │
│                   decision node                   │
│                        │                          │
│         ┌──────────────┴──────────────┐           │
│         ▼                             ▼           │
│   create_ticket               generate_answer     │
│         │                             │           │
│         └──────────────┬──────────────┘           │
│                        ▼                          │
│                 generate_answer                   │
└───────────────────────────────────────────────────┘
        │
        ▼
Structured JSON Response
```

---

## Project Structure

```
agentic-support-assignment/
├── mock-services/
│   ├── flowdesk.db          ← SQLite database (pre-seeded)
│   └── DB_SCHEMA.md         ← Schema reference
├── docs/                    ← Product documentation (10 markdown files)
│   ├── sso-setup-v2.md
│   ├── sso-setup-v3.md
│   ├── export-limits-v2.md
│   ├── export-limits-v3.md
│   ├── webhook-troubleshooting.md
│   ├── billing-refund-policy.md
│   ├── dashboard-known-issues.md
│   ├── release-notes-v3.1.md
│   ├── release-notes-v3.2.md
│   └── system-override.md   ← ADVERSARIAL (blocked by guard)
├── sample-requests/
│   └── example-queries.json ← 25 test cases
├── src/
│   ├── api/
│   │   ├── main.py          ← FastAPI entry point
│   │   ├── db.py            ← SQLite async connection
│   │   └── routes/
│   │       ├── customers.py
│   │       ├── plans.py
│   │       ├── incidents.py
│   │       ├── tickets.py
│   │       ├── knowledge_base.py
│   │       ├── diagnostics.py
│   │       └── support.py   ← POST /support/query
│   ├── agent/
│   │   ├── orchestrator.py  ← LangGraph workflow (main brain)
│   │   ├── state.py         ← Shared workflow state model
│   │   ├── intent_classifier.py
│   │   ├── decision.py      ← Escalation logic
│   │   └── prompts.py       ← All LLM prompts centralized
│   ├── rag/
│   │   ├── ingestion.py     ← LangChain markdown chunking
│   │   ├── embeddings.py    ← HuggingFace sentence-transformers
│   │   ├── vector_store.py  ← ChromaDB interface
│   │   ├── retriever.py     ← Hybrid dense + BM25 search
│   │   ├── reranker.py      ← Cross-encoder reranking
│   │   └── guard.py         ← Adversarial content detection
│   ├── tools/
│   │   ├── base.py          ← BaseTool with retry/timeout
│   │   ├── customer_tool.py
│   │   ├── plan_tool.py
│   │   ├── incident_tool.py
│   │   ├── ticket_tool.py
│   │   ├── knowledge_base_tool.py
│   │   └── diagnostic_tool.py
│   ├── models/
│   │   └── schemas.py       ← Shared Pydantic models
│   └── config.py            ← Central configuration
├── scripts/
│   └── ingest_docs.py       ← One-time RAG ingestion script
├── tests/
│   └── test_e2e.py          ← Dynamic E2E evaluation
├── app.py                   ← Streamlit UI
├── .env.example
├── requirements.txt         ← Backend dependencies (FastAPI, LangGraph, RAG, etc.)
├── requirements-ui.txt      ← Frontend dependencies (Streamlit + httpx only)
└── README.md
```

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| API Framework | FastAPI + Uvicorn |
| Database | SQLite (aiosqlite) |
| LLM Brain | OpenAI GPT-4o-mini |
| Orchestration | LangGraph |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| Vector Store | ChromaDB |
| Sparse Retrieval | BM25 (rank-bm25) |
| Reranking | CrossEncoder (ms-marco-MiniLM-L-6-v2) |
| Data Validation | Pydantic v2 |
| Retry Logic | tenacity |
| HTTP Client | httpx |
| UI | Streamlit (separate env — see Setup Guide) |

---

## Setup Guide

> **Note — Two virtual environments required**
> FastAPI pins `starlette < 0.42` while Streamlit 1.x requires `starlette >= 0.46`. These are mutually exclusive, so the backend and UI must run in separate virtual environments.

### Prerequisites

- Python 3.12
- OpenAI API key
- Git

### Step 1 — Clone the repository

```bash
git clone <repository-url>
cd agentic-support-assignment
```

### Step 2 — Create the backend environment

```bash
python -m venv ag_env
ag_env\Scripts\activate        # Windows
source ag_env/bin/activate     # macOS/Linux
pip install -r requirements.txt
```

### Step 3 — Create the UI environment (separate terminal)

```bash
python -m venv streamlit_env
streamlit_env\Scripts\activate        # Windows
source streamlit_env/bin/activate     # macOS/Linux
pip install -r requirements-ui.txt
```

### Step 4 — Configure environment

In the **backend** environment:

```bash
copy .env.example .env        # Windows
cp .env.example .env          # macOS/Linux
```

Open `.env` and set your OpenAI API key:

```env
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4o-mini
DB_PATH=mock-services/flowdesk.db
DOCS_DIR=docs
CHROMA_PERSIST_DIR=.chroma_store
```

### Step 5 — Ingest documents into vector store

Run this **once only** from the **backend** environment (`ag_env`). Loads all 10 markdown docs into ChromaDB:

```bash
python -m scripts.ingest_docs
```

Expected output:
```
[ingest] Done. Total chunks in store: 109
  billing-refund-policy.md          12 chunks
  sso-setup-v3.md                   15 chunks
  ...
```

---

## Running the System

### Start the API server

Activate the **backend** environment (`ag_env`), then:

```bash
python -m src.api.main
```

Server starts at `http://localhost:8001`. Swagger UI at `http://localhost:8001/docs`.

### Start the UI (separate terminal)

Activate the **UI** environment (`streamlit_env`), then:

```bash
streamlit run app.py
```

UI available at `http://localhost:8501`.

> The UI connects to the API at `http://localhost:8001` — make sure the API server is running first.

### Run E2E tests

Activate the **backend** environment (`ag_env`), then:

```bash
python -m tests.test_e2e
```

Runs all 25 test cases and saves `test_report.json`.

---

## API Reference

### Mock REST API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/customers/{customer_id}` | Get customer account details |
| GET | `/plans/{plan_name}` | Get plan features and limits |
| GET | `/plans/` | List all plans |
| GET | `/incidents/` | List incidents (filter by region, status) |
| GET | `/incidents/{incident_id}` | Get specific incident |
| POST | `/tickets/` | Create escalation ticket (idempotent) |
| GET | `/tickets/{ticket_id}` | Get ticket details |
| GET | `/knowledge-base/search` | Search product docs |
| POST | `/diagnostics/{customer_id}` | Run diagnostic checks |
| GET | `/health` | Health check |

### Support Agent Endpoint

```
POST /support/query
```

**Request:**
```json
{
  "customer_id": "cust_1024",
  "query": "Why is my CSV export failing? It has 63,000 rows."
}
```

**Response:**
```json
{
  "ticket_id": null,
  "customer_id": "cust_1024",
  "status": "resolved",
  "answer": "Your export contains 63,000 rows. Your Business plan supports up to 50,000 rows...",
  "confidence": 0.91,
  "escalation_required": false,
  "escalation_reason": null,
  "tools_used": [
    {"tool": "get_customer_account", "status": "success", "latency_ms": 45},
    {"tool": "search_knowledge_base", "status": "success", "latency_ms": 3500,
     "citations": ["export-limits-v3.md#Plan Limits"]}
  ],
  "execution_trace": [
    "Running security guard check",
    "Classified intent as csv_export_issue (confidence=0.95)",
    "Fetched customer plan (business) and version (3.2)",
    "Retrieved 3 knowledge base results",
    "Decision: auto-resolve — confidence 0.91",
    "Generated resolution with context-aware answer"
  ],
  "citations": [
    {"source": "export-limits-v3.md", "section": "Plan Limits", "relevance": 0.95}
  ]
}
```

---

## Agent Workflow

### Intent Classification

Every query is classified into one of 9 intents:

| Intent | Tool Chain |
|--------|-----------|
| `sso_setup` | customer → search_kb |
| `csv_export_issue` | customer + diagnostics (parallel) → search_kb |
| `incident_check` | customer → check_incidents → search_kb |
| `billing_refund` | customer → search_kb → **always escalate** |
| `webhook_issue` | customer + diagnostics (parallel) → search_kb |
| `plan_limits` | customer → fetch_plan → search_kb |
| `diagnostic_request` | customer → run_diagnostics |
| `general_question` | customer → search_kb |
| `adversarial` | **reject immediately** |

### Escalation Rules (applied in order)

1. Security threat detected → escalate
2. Intent is `billing_refund` or `adversarial` → escalate (policy-enforced)
3. Customer not found → escalate
4. Account suspended → escalate
5. No KB results for doc-dependent query → escalate
6. Confidence below 0.6 → escalate
7. Otherwise → auto-resolve

### Confidence Scoring

```
base score:        0.5
+ KB results:      up to +0.3 (normalized cross-encoder score)
+ customer data:   +0.1
+ diagnostics:     up to +0.05
+ intent score:    +0.1 × intent_confidence
─────────────────────────────
max:               ~1.0
```

---

## RAG Pipeline

### Document Processing

1. **Ingestion** — `MarkdownHeaderTextSplitter` splits docs at `#`, `##`, `###` headings preserving section metadata
2. **Chunking** — `RecursiveCharacterTextSplitter` further splits oversized sections (500 chars, 100 overlap)
3. **Metadata** — each chunk carries `source_file`, `category`, `version`, `section`, `is_adversarial`
4. **Storage** — ChromaDB stores embeddings + metadata, persisted to `.chroma_store/`

### Hybrid Retrieval

```
Query
  ├── Dense search (ChromaDB cosine similarity) — top 5
  └── Sparse search (BM25 keyword matching) — top 5
              │
              ▼
        Merge + deduplicate
              │
              ▼
   combined_score = 0.6 × dense + 0.4 × sparse
              │
              ▼
   Cross-encoder reranking (for complex intents)
              │
              ▼
        Guard filter
              │
              ▼
        Top 3 results
```

### Version Filtering

Customer version from the DB flows into every RAG query:
- v3.2 customer → filter: `version == "3.2" OR version == "3.x" OR version == "all"`
- Ensures v2 docs never appear for v3 customers

---

## Security

### Two-Layer Adversarial Protection

**Layer 1 — Query guard (before any tool call):**
- Regex patterns detect prompt injection (`ignore previous instructions`, `system override`, etc.)
- Regex patterns detect unauthorized access (`show all customers`, `reveal API keys`, etc.)
- Queries over 1000 characters are flagged
- High-threat queries → immediate rejection, no tools called

**Layer 2 — RAG guard (at retrieval):**
- `is_adversarial=0` filter applied at ChromaDB level — adversarial chunks never retrieved
- `system-override.md` blocked by source blocklist in config
- Any adversarial content that passes DB filter is caught by `filter_results()`

### Idempotent Ticket Creation

Tickets use an idempotency key (`customer_id + intent + query[:30]`). Duplicate requests return the existing ticket instead of creating a new one.

---

## Test Results

Running `python -m tests.test_e2e` against all 25 example queries:

```
Total    : 25
Passed   : 22 (88.0%)
Failed   : 3
Errors   : 0

By Difficulty:
  EASY   : 5/5  passed
  MEDIUM : 11/12 passed
  HARD   : 6/8  passed

Minimum required: 15
Result: ✓ PASSED
```

### Failed Cases Analysis

| ID | Reason |
|----|--------|
| `q06_webhook_insufficient_info` | Agent provided helpful answer instead of escalating — arguably better behavior |
| `q18_downgrade_refund` | Query mentions "refund" → classified as `billing_refund` → escalated per policy. Test expected no escalation but policy enforcement is correct |
| `q20_ambiguous_query` | "It's broken. Fix it." — confidence 0.66 just above 0.6 threshold. Borderline case |

---

## Design Decisions

### Why LangGraph over ReAct agent?

LangGraph provides explicit graph-based routing that is deterministic and testable. A ReAct agent would use the LLM to decide each tool call, which is less predictable and harder to enforce policies like "always escalate refunds." LangGraph gives us full control over the workflow while still being dynamic via conditional edges.

### Why not call all tools for every query?

The requirement explicitly forbids this. Intent classification drives dynamic tool selection — an SSO setup question never calls the incident or diagnostics API. This reduces latency, cost, and the risk of irrelevant context polluting the LLM prompt.

### Why hybrid retrieval instead of pure vector search?

Dense embeddings capture semantic similarity but miss exact keyword matches (e.g., error code "FD-4297"). BM25 captures exact keywords but misses semantic meaning. Combining both with a 60/40 weighting gives the best of both worlds.

### Why cross-encoder reranking?

Bi-encoder embeddings score query and document independently. Cross-encoder reads them together and scores relevance more accurately — it understands "does this chunk actually answer this specific question?" We apply it selectively only for complex intents to manage latency.

### Why store JSON fields as TEXT in SQLite?

SQLite has no native JSON column type. Fields like `features` and `limits` are stored as JSON strings. The API layer deserializes them before serving, so the client always receives proper JSON objects.

### Why sentence-transformers locally instead of OpenAI embeddings?

`all-MiniLM-L6-v2` runs fully locally — no API cost, no network latency for embedding generation, and no external dependency for the RAG pipeline. For 109 chunks at this scale, local embeddings are the right tradeoff.

---

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | required | OpenAI API key |
| `OPENAI_MODEL` | `gpt-4o-mini` | LLM model |
| `OPENAI_MAX_TOKENS` | `1500` | Max response tokens |
| `OPENAI_TEMPERATURE` | `0.0` | LLM temperature |
| `API_HOST` | `0.0.0.0` | API server host |
| `API_PORT` | `8001` | API server port |
| `DB_PATH` | `mock-services/flowdesk.db` | SQLite path |
| `DOCS_DIR` | `docs` | Markdown docs directory |
| `CHROMA_PERSIST_DIR` | `.chroma_store` | ChromaDB storage |
| `CHROMA_COLLECTION_NAME` | `flowdesk_docs` | Collection name |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Embedding model |
| `RAG_TOP_K_DENSE` | `5` | Dense retrieval top-k |
| `RAG_TOP_K_SPARSE` | `5` | BM25 retrieval top-k |
| `RAG_TOP_K_FINAL` | `3` | Final results after reranking |
| `RAG_MIN_RELEVANCE_SCORE` | `0.3` | Minimum relevance threshold |
| `TOOL_MAX_RETRIES` | `3` | Tool retry attempts |
| `TOOL_RETRY_BASE_DELAY` | `1.0` | Backoff base delay (seconds) |
| `TOOL_TIMEOUT_SECONDS` | `10.0` | Per-tool timeout |
| `AGENT_MIN_CONFIDENCE` | `0.6` | Auto-resolve threshold |
| `AGENT_MAX_TOOL_CALLS` | `10` | Max tool calls per query |
| `BLOCKED_DOC_SOURCES` | `system-override.md` | Adversarial doc blocklist |
| `LOG_LEVEL` | `INFO` | Logging level |
