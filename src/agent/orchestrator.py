"""
src/agent/orchestrator.py
─────────────────────────
LangGraph-based orchestrator agent.
Receives {customer_id, query} and produces a structured resolution.
"""

import json
import logging
import asyncio
from typing import Literal
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from src.agent.state import AgentState
from src.agent.intent_classifier import classify_intent
from src.agent.decision import evaluate
from src.agent.prompts import (
    ANSWER_GENERATION_PROMPT,
    format_kb_context,
    format_incident_context,
    format_diagnostic_context,
    format_customer_context,
)
from src.rag.guard import inspect_query
from src.tools.customer_tool import CustomerTool
from src.tools.plan_tool import PlanTool
from src.tools.incident_tool import IncidentTool
from src.tools.ticket_tool import TicketTool
from src.tools.knowledge_base_tool import KnowledgeBaseTool
from src.tools.diagnostic_tool import DiagnosticTool
from src.rag.ingestion import load_chunks
from src.rag.retriever import build_bm25_index
from src.config import settings
from src.models.schemas import SupportQueryResponse, ToolUsed, Citation

logger = logging.getLogger(__name__)

# ── Tool instances ────────────────────────────────────────────────
customer_tool = CustomerTool()
plan_tool = PlanTool()
incident_tool = IncidentTool()
ticket_tool = TicketTool()
kb_tool = KnowledgeBaseTool()
diagnostic_tool = DiagnosticTool()

# ── LLM ──────────────────────────────────────────────────────────
llm = ChatOpenAI(
    model=settings.openai_model,
    temperature=0.0,
    max_tokens=settings.openai_max_tokens,
    api_key=settings.openai_api_key,
)

# ── BM25 init flag ────────────────────────────────────────────────
_bm25_initialized = False

def _ensure_bm25():
    global _bm25_initialized
    if not _bm25_initialized:
        chunks = load_chunks()
        build_bm25_index(chunks)
        _bm25_initialized = True


# ══════════════════════════════════════════════════════════════════
# NODE FUNCTIONS
# ══════════════════════════════════════════════════════════════════

def node_guard(state: AgentState) -> AgentState:
    """Security check — runs before anything else."""
    state.add_trace("Running security guard check")
    result = inspect_query(state.query)
    state.threat_level = result["threat_level"]
    state.injection_detected = result["injection_detected"]
    state.unauthorized_access = result["unauthorized_access"]

    if not result["safe"]:
        state.add_trace(f"Guard: threat detected — level={result['threat_level']}")
    return state


def node_classify_intent(state: AgentState) -> AgentState:
    """Classify query intent."""
    state.add_trace("Classifying query intent")
    result = classify_intent(state.query)
    state.intent = result["intent"]
    state.intent_confidence = result["confidence"]
    state.add_trace(f"Classified intent as {state.intent} (confidence={state.intent_confidence})")
    return state


async def node_fetch_customer(state: AgentState) -> AgentState:
    """Fetch customer account details."""
    state.add_trace(f"Fetching customer account for {state.customer_id}")
    result = await customer_tool.run(customer_id=state.customer_id)
    state.add_tool("get_customer_account", "success" if result.success else "error", result.latency_ms)

    if result.success:
        state.customer = result.data
        state.add_trace(
            f"Fetched customer plan ({result.data['plan']}) "
            f"and version ({result.data['product_version']})"
        )
    else:
        state.add_error(f"Customer lookup failed: {result.error}")
        state.add_trace(f"Customer lookup failed: {result.error}")

    return state


async def node_fetch_plan(state: AgentState) -> AgentState:
    """Fetch plan details for limit/feature queries."""
    if not state.customer:
        return state

    plan_name = state.customer.get("plan")
    state.add_trace(f"Fetching plan details for {plan_name}")
    result = await plan_tool.run(plan_name=plan_name)
    state.add_tool("get_plan_details", "success" if result.success else "error", result.latency_ms)

    if result.success:
        state.plan = result.data
        state.add_trace(f"Retrieved plan details for {plan_name}")
    else:
        state.add_error(f"Plan lookup failed: {result.error}")

    return state


async def node_search_kb(state: AgentState) -> AgentState:
    """Search knowledge base with version and category filters."""
    if not state.customer:
        version = None
        category = None
    else:
        version = state.customer.get("product_version")
        category = _intent_to_category(state.intent)

    state.add_trace(f"Searching knowledge base (version={version}, category={category})")
    result = await kb_tool.run(query=state.query, version=version, category=category, intent=state.intent)
    state.add_tool(
        "search_knowledge_base",
        "success" if result.success else "error",
        result.latency_ms,
        citations=[
            f"{r['source_file']}#{r['section']}"
            for r in (result.data or [])
        ],
    )

    if result.success:
        state.kb_results = result.data
        state.add_trace(f"Retrieved {len(result.data)} knowledge base results")
        if result.data:
            state.add_trace(
                f"Retrieved policy for {result.data[0]['source_file']} — {result.data[0]['section']}"
            )
    else:
        state.add_error(f"KB search failed: {result.error}")

    return state


async def node_check_incidents(state: AgentState) -> AgentState:
    """Check for active incidents in customer's region."""
    if not state.customer:
        return state

    region = state.customer.get("region")
    state.add_trace(f"Checking active incidents for region {region}")
    result = await incident_tool.run(region=region, active_only=True)
    state.add_tool("check_incidents", "success" if result.success else "error", result.latency_ms)

    if result.success:
        state.incidents = result.data
        if result.data:
            state.add_trace(
                f"Found active incident {result.data[0]['incident_id']} in region {region}"
            )
        else:
            state.add_trace(f"No active incidents in region {region}")
    else:
        state.add_error(f"Incident check failed: {result.error}")

    return state


async def node_run_diagnostics(state: AgentState) -> AgentState:
    """Run diagnostic checks for technical issues."""
    if not state.customer:
        return state

    state.add_trace(f"Running diagnostics for {state.customer_id}")
    result = await diagnostic_tool.run(customer_id=state.customer_id)
    state.add_tool("run_diagnostics", "success" if result.success else "error", result.latency_ms)

    if result.success:
        state.diagnostics = result.data
        state.add_trace("Diagnostic checks completed")
    else:
        state.add_error(f"Diagnostics failed: {result.error}")

    return state




async def node_fetch_customer_and_diagnostics(state: AgentState) -> AgentState:
    """Fetch customer and run diagnostics in parallel — for export/webhook intents."""
    state.add_trace(f"Fetching customer account and running diagnostics in parallel")

    async def fetch_customer():
        result = await customer_tool.run(customer_id=state.customer_id)
        state.add_tool("get_customer_account", "success" if result.success else "error", result.latency_ms)
        if result.success:
            state.customer = result.data
            state.add_trace(f"Fetched customer plan ({result.data['plan']}) and version ({result.data['product_version']})")
        else:
            state.add_error(f"Customer lookup failed: {result.error}")
        return result

    async def fetch_diagnostics():
        result = await diagnostic_tool.run(customer_id=state.customer_id)
        state.add_tool("run_diagnostics", "success" if result.success else "error", result.latency_ms)
        if result.success:
            state.diagnostics = result.data
            state.add_trace("Diagnostic checks completed")
        else:
            state.add_error(f"Diagnostics failed: {result.error}")
        return result

    await asyncio.gather(fetch_customer(), fetch_diagnostics())
    return state

def node_decision(state: AgentState) -> AgentState:
    """Evaluate state and decide resolution vs escalation."""
    state.add_trace("Evaluating resolution confidence and escalation criteria")
    return evaluate(state)


async def node_create_ticket(state: AgentState) -> AgentState:
    """Create escalation ticket if required."""
    if not state.should_escalate:
        return state

    idempotency_key = f"{state.customer_id}_{state.intent}_{state.query[:30].replace(' ', '_')}"
    state.add_trace("Creating escalation ticket")

    result = await ticket_tool.run(
        customer_id=state.customer_id,
        summary=f"[{state.intent}] {state.query[:200]}",
        category=_intent_to_category(state.intent) or "general",
        priority=_intent_to_priority(state.intent),
        evidence=[
            f"Intent: {state.intent}",
            f"Escalation reason: {state.escalation_reason}",
            f"Confidence: {state.confidence}",
        ],
        assigned_team=_intent_to_team(state.intent),
        idempotency_key=idempotency_key,
    )
    state.add_tool("create_ticket", "success" if result.success else "error", result.latency_ms)

    if result.success:
        state.ticket_id = result.data["ticket_id"]
        state.add_trace(f"Escalation ticket created: {state.ticket_id}")
    else:
        state.add_error(f"Ticket creation failed: {result.error}")

    return state


async def node_generate_answer(state: AgentState) -> AgentState:
    """Generate final customer-facing answer using GPT."""
    state.add_trace("Generating final response")

    if state.should_escalate:
        state.answer = _escalation_message(state)
        state.status = "escalated"
        state.add_trace("Generated escalation response")
        return state

    customer = state.customer or {}
    prompt = ANSWER_GENERATION_PROMPT.format(
        customer_id=state.customer_id,
        plan=customer.get("plan", "unknown"),
        version=customer.get("product_version", "unknown"),
        region=customer.get("region", "unknown"),
        query=state.query,
        intent=state.intent,
        customer_context=format_customer_context(state.customer, state.plan),
        kb_context=format_kb_context(state.kb_results),
        incident_context=format_incident_context(state.incidents),
        diagnostic_context=format_diagnostic_context(state.diagnostics),
    )

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        state.answer = response.content
        state.add_trace("Generated resolution with context-aware answer")
    except Exception as e:
        logger.error(f"Answer generation failed: {e}")
        state.answer = "We encountered an issue generating a response. Please contact support."
        state.should_escalate = True
        state.escalation_reason = "Answer generation failed"

    # Build citations
    state.citations = [
        {
            "source": r["source_file"],
            "section": r["section"],
            "relevance": round(min(max((r.get("rerank_score", 0) + 5) / 15, 0.0), 1.0), 3),
        }
        for r in state.kb_results
    ]

    state.status = "escalated" if state.should_escalate else "resolved"
    return state


# ══════════════════════════════════════════════════════════════════
# ROUTING FUNCTIONS
# ══════════════════════════════════════════════════════════════════

def route_after_guard(state: AgentState) -> Literal["classify", "reject"]:
    if state.threat_level == "high":
        return "reject"
    return "classify"


def route_after_intent(state: AgentState) -> Literal[
    "fetch_customer", "reject"
]:
    if state.intent == "adversarial":
        return "reject"
    return "fetch_customer"


def route_after_customer(state: AgentState) -> Literal[
    "search_kb", "check_incidents", "run_diagnostics", "fetch_customer_and_diagnostics", "fetch_plan", "decision"
]:
    intent = state.intent

    if intent in ("sso_setup", "general_question", "billing_refund"):
        return "search_kb"
    if intent == "incident_check":
        return "check_incidents"
    if intent in ("csv_export_issue", "webhook_issue"):
        return "fetch_customer_and_diagnostics"
    if intent == "diagnostic_request":
        return "run_diagnostics"
    if intent == "plan_limits":
        return "fetch_plan"
    return "search_kb"


def route_after_diagnostics(state: AgentState) -> Literal["search_kb", "decision"]:
    if state.intent in ("csv_export_issue", "webhook_issue"):
        return "search_kb"
    return "decision"


def route_after_incidents(state: AgentState) -> Literal["search_kb", "decision"]:
    return "search_kb"


def route_after_plan(state: AgentState) -> Literal["search_kb"]:
    return "search_kb"


def route_after_decision(state: AgentState) -> Literal["create_ticket", "generate_answer"]:
    if state.should_escalate:
        return "create_ticket"
    return "generate_answer"


def node_reject(state: AgentState) -> AgentState:
    """Handle rejected/adversarial queries."""
    state.status = "rejected"
    state.should_escalate = True
    state.escalation_reason = "Unauthorized or adversarial request detected"
    state.confidence = 0.0
    state.answer = (
        "This request cannot be processed. "
        "If you believe this is an error, please contact support directly."
    )
    state.add_trace("Request rejected — security policy violation")
    return state


# ══════════════════════════════════════════════════════════════════
# GRAPH ASSEMBLY
# ══════════════════════════════════════════════════════════════════

def build_graph():
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("guard", node_guard)
    graph.add_node("classify", node_classify_intent)
    graph.add_node("fetch_customer", node_fetch_customer)
    graph.add_node("fetch_plan", node_fetch_plan)
    graph.add_node("search_kb", node_search_kb)
    graph.add_node("check_incidents", node_check_incidents)
    graph.add_node("run_diagnostics", node_run_diagnostics)
    graph.add_node("fetch_customer_and_diagnostics", node_fetch_customer_and_diagnostics)
    graph.add_node("decision", node_decision)
    graph.add_node("create_ticket", node_create_ticket)
    graph.add_node("generate_answer", node_generate_answer)
    graph.add_node("reject", node_reject)

    # Entry point
    graph.set_entry_point("guard")

    # Edges
    graph.add_conditional_edges("guard", route_after_guard, {
        "classify": "classify",
        "reject": "reject",
    })
    graph.add_conditional_edges("classify", route_after_intent, {
        "fetch_customer": "fetch_customer",
        "reject": "reject",
    })
    graph.add_conditional_edges("fetch_customer", route_after_customer, {
        "search_kb": "search_kb",
        "check_incidents": "check_incidents",
        "run_diagnostics": "run_diagnostics",
        "fetch_customer_and_diagnostics": "fetch_customer_and_diagnostics",
        "fetch_plan": "fetch_plan",
        "decision": "decision",
    })
    graph.add_edge("fetch_customer_and_diagnostics", "search_kb")
    graph.add_conditional_edges("run_diagnostics", route_after_diagnostics, {
        "search_kb": "search_kb",
        "decision": "decision",
    })
    graph.add_conditional_edges("check_incidents", route_after_incidents, {
        "search_kb": "search_kb",
        "decision": "decision",
    })
    graph.add_conditional_edges("fetch_plan", route_after_plan, {
        "search_kb": "search_kb",
    })
    graph.add_edge("search_kb", "decision")
    graph.add_conditional_edges("decision", route_after_decision, {
        "create_ticket": "create_ticket",
        "generate_answer": "generate_answer",
    })
    graph.add_edge("create_ticket", "generate_answer")
    graph.add_edge("generate_answer", END)
    graph.add_edge("reject", END)

    return graph.compile()


# ── Compiled graph singleton ──────────────────────────────────────
_graph = None

def get_graph():
    global _graph
    if _graph is None:
        _ensure_bm25()
        _graph = build_graph()
    return _graph


# ══════════════════════════════════════════════════════════════════
# PUBLIC ENTRY POINT
# ══════════════════════════════════════════════════════════════════

async def run_agent(customer_id: str, query: str) -> SupportQueryResponse:
    """
    Main entry point for the orchestrator.
    Called by POST /support/query.
    """
    graph = get_graph()

    initial_state = AgentState(customer_id=customer_id, query=query)
    result = await graph.ainvoke(initial_state)

    # LangGraph returns AddableValuesDict — access via .get()
    return SupportQueryResponse(
        ticket_id=result.get("ticket_id"),
        customer_id=result.get("customer_id", customer_id),
        status=result.get("status", "error"),
        answer=result.get("answer", ""),
        confidence=result.get("confidence", 0.0),
        escalation_required=result.get("should_escalate", False),
        escalation_reason=result.get("escalation_reason"),
        tools_used=[ToolUsed(**t) for t in result.get("tools_used", [])],
        execution_trace=result.get("execution_trace", []),
        citations=[Citation(**c) for c in result.get("citations", [])],
    )


# ══════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════

def _intent_to_category(intent: str) -> str | None:
    mapping = {
        "sso_setup": "authentication",
        "csv_export_issue": "exports",
        "webhook_issue": "integrations",
        "billing_refund": "billing",
        "incident_check": "dashboard",
        "plan_limits": None,
        "general_question": None,
    }
    return mapping.get(intent)


def _intent_to_priority(intent: str) -> str:
    high = {"billing_refund", "adversarial", "incident_check"}
    return "high" if intent in high else "medium"


def _intent_to_team(intent: str) -> str:
    mapping = {
        "billing_refund": "billing",
        "adversarial": "security",
        "incident_check": "infrastructure",
        "sso_setup": "support",
    }
    return mapping.get(intent, "support")


def _escalation_message(state: AgentState) -> str:
    if "too vague" in (state.escalation_reason or ""):
        return (
            "Your query doesn't have enough detail for us to assist you automatically. "
            f"A support ticket ({state.ticket_id}) has been created. "
            "Please provide more details about your issue and our team will contact you shortly."
        )
    if state.intent == "billing_refund":
        return (
            "Refund requests must be reviewed and processed by our billing team. "
            f"A support ticket ({state.ticket_id}) has been created and our team "
            "will contact you within 1-2 business days."
        )
    if state.intent == "adversarial" or state.threat_level in ("high", "medium"):
        return "This request cannot be processed due to security policy restrictions."
    return (
        f"Your query has been escalated to our support team. "
        f"Ticket {state.ticket_id} has been created. "
        f"Reason: {state.escalation_reason}"
    )