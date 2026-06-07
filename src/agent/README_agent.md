# src/agent — Orchestrator Agent

The brain of the system. Receives `{customer_id, query}` and produces a structured resolution using a LangGraph workflow.

---

## Files

### `state.py`
Single Pydantic model (`AgentState`) passed between all LangGraph nodes. Acts as shared memory across the entire workflow — every node reads what it needs and writes its results back.

**Field groups:**
| Group | Fields | Set by |
|-------|--------|--------|
| Input | `customer_id`, `query` | Entry point, never changed |
| Security | `threat_level`, `injection_detected`, `unauthorized_access` | `node_guard` |
| Intent | `intent`, `intent_confidence` | `node_classify_intent` |
| Customer context | `customer`, `plan` | `node_fetch_customer`, `node_fetch_plan` |
| Tool results | `kb_results`, `incidents`, `diagnostics` | Tool nodes |
| Tool trace | `tools_used` | Every tool node via `add_tool()` |
| Decision | `should_escalate`, `escalation_reason`, `confidence` | `node_decision` |
| Output | `answer`, `ticket_id`, `citations`, `status` | `node_generate_answer` |
| Errors | `errors` | Any node on failure |

**Helper methods:**
- `add_trace(msg)` — appends to `execution_trace` array in final response
- `add_tool(tool, status, latency_ms, citations)` — records tool call in `tools_used`
- `add_error(msg)` — logs non-fatal errors

---

### `intent_classifier.py`
Classifies the incoming query into one of 9 intents using GPT-4o-mini with `temperature=0.0` and `response_format=json_object`.

**9 valid intents:**
| Intent | Triggered by |
|--------|-------------|
| `sso_setup` | SAML SSO configuration questions |
| `csv_export_issue` | Export failures, row limits, FD-4297 |
| `incident_check` | Slow dashboard, outages, performance |
| `billing_refund` | Refund requests, invoice questions |
| `webhook_issue` | Webhook delivery failures |
| `plan_limits` | Plan features, upgrade/downgrade questions |
| `diagnostic_request` | Explicit requests to run checks |
| `general_question` | General how-to questions |
| `adversarial` | Unauthorized access, prompt injection |

Falls back to `general_question` with confidence 0.3 if classification fails.

---

### `prompts.py`
All LLM prompts centralized in one file. Never scattered across modules.

**Three prompts:**
- `INTENT_CLASSIFICATION_PROMPT` — classifies query, returns JSON `{intent, confidence, reasoning}`
- `ANSWER_GENERATION_PROMPT` — generates customer-facing answer using all gathered context. Has hard rules: no refunds, no other customer data, no fabrication, no email signatures
- `ESCALATION_DECISION_PROMPT` — evaluates whether to escalate (used as backup logic)

**Four context formatters:**
- `format_kb_context(results)` — formats RAG results as readable doc excerpts
- `format_incident_context(incidents)` — formats active incidents as bullet list
- `format_diagnostic_context(diagnostics)` — formats health check results
- `format_customer_context(customer, plan)` — formats customer plan/features/limits

---

### `decision.py`
Pure rule-based escalation logic. No LLM call. Fast and deterministic.

**8 rules applied in strict order — first match wins:**
```
1. threat_level high/medium OR injection_detected → escalate (security)
2. intent is billing_refund OR adversarial → escalate (policy)
3. customer is None → escalate (not found)
4. customer.status == suspended → escalate
5. doc-dependent intent + no KB results → escalate
6. active incident found → inform only, continue
7. confidence < 0.6 → escalate
8. all rules passed → auto-resolve
```

**Confidence computation:**
```python
score = 0.5 (base)
score += 0.3 * normalize(kb_results[0].rerank_score)  # top KB result quality
score += 0.1  # if customer data available
score += 0.05 * (ok_checks / total_checks)            # diagnostic health
score += 0.1 * intent_confidence                       # classifier confidence
```

---

### `orchestrator.py`
Main LangGraph workflow. The most complex file in the system.

**Graph nodes:**

| Node | Function | Always runs? |
|------|----------|-------------|
| `guard` | Security check via `inspect_query()` | Yes |
| `classify` | Intent classification via GPT-4o-mini | Yes (unless rejected) |
| `fetch_customer` | CustomerTool call | Yes (unless rejected) |
| `fetch_plan` | PlanTool call | Only for `plan_limits` intent |
| `search_kb` | KnowledgeBaseTool — hybrid RAG search | Most intents |
| `check_incidents` | IncidentTool filtered by customer region | Only `incident_check` |
| `run_diagnostics` | DiagnosticTool | Only `diagnostic_request` |
| `fetch_customer_and_diagnostics` | Both in parallel via `asyncio.gather` | `csv_export_issue`, `webhook_issue` |
| `decision` | Escalation evaluation via `decision.py` | Yes |
| `create_ticket` | TicketTool with idempotency key | Only if escalating |
| `generate_answer` | GPT-4o-mini answer generation | Yes |
| `reject` | Immediate rejection response | Only for adversarial/high-threat |

**Routing logic:**
```
guard → high threat? → reject
      → safe? → classify

classify → adversarial intent? → reject
         → other intent? → fetch_customer

fetch_customer → intent routing:
  sso_setup / general_question / billing_refund → search_kb
  incident_check → check_incidents → search_kb
  csv_export_issue / webhook_issue → fetch_customer_and_diagnostics → search_kb
  plan_limits → fetch_plan → search_kb
  diagnostic_request → run_diagnostics → decision

search_kb → decision
decision → escalate? → create_ticket → generate_answer
         → resolve? → generate_answer
generate_answer → END
reject → END
```

**Public entry point:**
```python
async def run_agent(customer_id: str, query: str) -> SupportQueryResponse
```
Called by `POST /support/query`. Creates initial `AgentState`, runs through full graph, maps result dict to `SupportQueryResponse`.
