# src/api — Mock REST API

Thin FastAPI layer over the SQLite database. Serves all data the orchestrator needs via HTTP endpoints.

---

## Files

### `main.py`
FastAPI application entry point. Registers all routers, adds CORS middleware, request logging middleware, and global exception handler. Run with:
```bash
python -m src.api.main
```

### `db.py`
Async SQLite connection layer using `aiosqlite`.

Key functions:
- `get_db()` — async context manager returning a database connection
- `fetchone(query, params)` — returns single row as dict or None
- `fetchall(query, params)` — returns list of dicts
- `execute(query, params)` — runs INSERT/UPDATE/DELETE, returns lastrowid
- `parse_json_fields(row, fields)` — deserializes TEXT-stored JSON fields into Python dicts

**Important:** SQLite stores `features`, `limits`, `restrictions`, `evidence`, `affects_plans` as JSON strings. Always call `parse_json_fields()` before returning these to clients.

---

## routes/

### `customers.py`
```
GET /customers/{customer_id}
```
Returns full customer record with deserialized JSON fields. Returns 404 if not found.

**Response fields:** `customer_id`, `company_name`, `plan`, `product_version`, `region`, `features` (dict), `limits` (dict), `created_at`, `status`

---

### `plans.py`
```
GET /plans/{plan_name}
GET /plans/
```
Returns plan catalog details. `plan_name` is one of: `starter`, `pro`, `business`, `enterprise`.

**Response fields:** `plan_name`, `display_name`, `features` (dict), `limits` (dict), `restrictions` (dict)

---

### `incidents.py`
```
GET /incidents/?region=ap-south-1&active_only=true
GET /incidents/{incident_id}
```
Query parameters:
- `region` — filters by region OR `global` incidents
- `active_only` — returns only `investigating`, `identified`, `monitoring` statuses
- `status` — filter by specific status

---

### `tickets.py`
```
POST /tickets/
GET  /tickets/{ticket_id}
```
**Idempotency:** If `idempotency_key` is provided and a ticket with that key already exists, returns the existing ticket instead of creating a new one. This prevents duplicate tickets on retries.

Ticket ID format: `TKT-{timestamp}` auto-generated.

---

### `knowledge_base.py`
```
GET /knowledge-base/search?q=sso&version=3.x&category=authentication
```
Query parameters:
- `q` — keyword search across title, content, section
- `category` — filter by category (authentication, exports, billing, etc.)
- `version` — supports exact (`3.2`) or major (`3.x`) matching, always includes `all`
- `exclude_adversarial` — defaults to True, filters out `is_adversarial=1` documents

**Note:** This is a simple SQL keyword search. The full semantic RAG search is in `src/rag/`.

---

### `diagnostics.py`
```
POST /diagnostics/{customer_id}
```
Runs 4 simulated health checks against the customer's feature flags and limits:
- `export_health` — checks if CSV export is enabled, returns row limit
- `auth_config` — checks SAML SSO status
- `webhooks` — checks webhook delivery status
- `dashboard_latency` — simulates response time (random 10-120ms, degraded if >100ms)

Results are simulated — latency values are random on each call.

---

### `support.py`
```
POST /support/query
```
The main agent endpoint. Receives `{customer_id, query}`, calls `run_agent()` from the orchestrator, returns structured `SupportQueryResponse`. This is the only route that involves LLM calls.
