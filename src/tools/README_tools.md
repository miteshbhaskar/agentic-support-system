# src/tools — Tool Wrappers

Callable tools the orchestrator uses to interact with the REST API and RAG pipeline. Each tool wraps a specific capability with retry logic, timeout, and response validation.

---

## How Tools Work

Every tool inherits from `BaseTool` and follows this pattern:

```
orchestrator calls tool.run(**kwargs)
        │
        ▼
BaseTool.run() — handles timing, retry loop, error wrapping
        │
        ▼
tool._execute(**kwargs) — actual logic (HTTP call or RAG search)
        │
        ▼
returns ToolResult(success, data, error, latency_ms)
```

The orchestrator always receives a `ToolResult` — it never crashes from a tool failure. It checks `result.success` and decides what to do.

---

## `base.py`

**`ToolError(tool_name, message, retryable)`**
Custom exception. `retryable=True` means the retry loop will try again. `retryable=False` means fail immediately (e.g. 404 not found — retrying won't help).

**`ToolResult`**
Data carrier returned by every tool call:
- `success` — True/False
- `data` — the actual result (dict or list)
- `error` — error message if failed
- `latency_ms` — total execution time
- `to_trace_dict()` — formats for `tools_used` in final JSON response

**`BaseTool.run()`**
Retry loop with exponential backoff:
```
attempt 1 → wait 1s → attempt 2 → wait 2s → attempt 3 → fail
```
Timeouts and network errors are retryable. Validation errors and 404s are not.

---

## `customer_tool.py` — `CustomerTool`

**Input:** `customer_id: str`
**Output:** customer dict with deserialized `features` and `limits`

Calls `GET /customers/{customer_id}`. Validates all required fields are present in response. 404 → non-retryable ToolError.

---

## `plan_tool.py` — `PlanTool`

**Input:** `plan_name: str`
**Output:** plan dict with `features`, `limits`, `restrictions`

Validates `plan_name` is one of `{starter, pro, business, enterprise}` before making the HTTP call — fails fast without hitting the API for invalid input.

---

## `incident_tool.py` — `IncidentTool`

**Input:** `region: str | None`, `active_only: bool = True`
**Output:** list of incident dicts

Calls `GET /incidents/` with query parameters. `active_only=True` filters to `investigating`, `identified`, `monitoring` statuses. When `region` is provided, returns incidents for that region plus any `global` incidents.

---

## `ticket_tool.py` — `TicketTool`

**Input:** `customer_id`, `summary`, `category`, `priority`, `evidence`, `assigned_team`, `idempotency_key`
**Output:** created (or existing) ticket dict

**Idempotency:** If `idempotency_key` is provided and a ticket already exists with that key, the API returns the existing ticket. This means the orchestrator can safely retry ticket creation without creating duplicates.

Idempotency key format used by orchestrator: `{customer_id}_{intent}_{query[:30]}`

---

## `knowledge_base_tool.py` — `KnowledgeBaseTool`

**Input:** `query`, `version`, `category`, `intent`
**Output:** list of ranked result dicts

Full RAG pipeline in one tool call:
1. `hybrid_search(query, version, category)` — dense + BM25
2. `rerank(query, results)` — cross-encoder (only for complex intents)
3. `filter_results(results)` — removes adversarial content

**Selective reranking:** Cross-encoder only runs for `sso_setup`, `csv_export_issue`, `webhook_issue`, `plan_limits`. Simple intents use `combined_score` directly — saves ~2s latency.

**Each result dict contains:**
```python
{
  "text": "...",           # chunk content
  "source_file": "...",    # e.g. export-limits-v3.md
  "section": "...",        # section heading
  "category": "...",       # e.g. exports
  "version": "...",        # e.g. 3.x
  "is_adversarial": False,
  "dense_score": 0.83,
  "sparse_score": 0.6,
  "combined_score": 0.74,
  "rerank_score": 5.11,    # cross-encoder logit
}
```

---

## `diagnostic_tool.py` — `DiagnosticTool`

**Input:** `customer_id: str`
**Output:** dict with `customer_id` and list of `checks`

Calls `POST /diagnostics/{customer_id}`. Returns 4 simulated health checks based on customer's actual feature flags from the database:

| Check | What it tests |
|-------|--------------|
| `export_health` | Is CSV export enabled? What is the row limit? |
| `auth_config` | Is SAML SSO enabled or disabled? |
| `webhooks` | Is webhook delivery active? |
| `dashboard_latency` | Simulated response time (ok < 100ms, degraded ≥ 100ms) |

---

## Tool → Team Routing (for ticket creation)

| Intent | Priority | Assigned Team |
|--------|----------|--------------|
| `billing_refund` | high | billing |
| `adversarial` | high | security |
| `incident_check` | high | infrastructure |
| `sso_setup` | medium | support |
| all others | medium | support |
