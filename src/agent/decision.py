"""
src/agent/decision.py
─────────────────────
Escalation and confidence decision logic.
Determines whether a query can be auto-resolved or needs human escalation.
"""

import logging
from src.agent.state import AgentState

logger = logging.getLogger(__name__)

# Intents that ALWAYS escalate regardless of confidence
ALWAYS_ESCALATE_INTENTS = {"billing_refund", "adversarial"}

# Minimum KB results needed to attempt auto-resolution
MIN_KB_RESULTS = 1

VAGUE_INTENTS = {"general_question", "diagnostic_request"}

def evaluate(state: AgentState) -> AgentState:
    """
    Evaluates the current state and decides:
    - should_escalate: True/False
    - escalation_reason: why escalation is needed
    - confidence: how confident we are in auto-resolution

    Rules applied in order (first match wins):
    1. Security threat → always escalate
    2. Always-escalate intents (billing_refund, adversarial)
    3. Customer not found → escalate
    4. Customer suspended → escalate
    5. No KB results found → escalate
    6. Active incident found → inform but don't escalate
    7. Confidence below threshold → escalate
    8. Otherwise → auto-resolve
    """

    # Rule 1 — Security threat
    if state.threat_level in ("high", "medium") or state.injection_detected:
        state.should_escalate = True
        state.escalation_reason = "Security threat detected in query"
        state.confidence = 0.0
        state.add_trace("Decision: escalate — security threat detected")
        return state

    # Add this as Rule 1.5 — after security check, before always-escalate
    if state.intent in VAGUE_INTENTS and (state.intent_confidence < 0.85 or len(state.query.split()) <= 3):
        state.should_escalate = True
        state.escalation_reason = "Query is too vague to resolve automatically. Please provide more details."
        state.confidence = 0.0
        state.add_trace("Decision: escalate — query too vague")
        return state

    # Rule 2 — Always-escalate intents
    if state.intent in ALWAYS_ESCALATE_INTENTS:
        state.should_escalate = True
        state.escalation_reason = (
            "Refund requests must be processed by a human agent"
            if state.intent == "billing_refund"
            else "Unauthorized access attempt detected"
        )
        state.confidence = 0.0
        state.add_trace(f"Decision: escalate — intent '{state.intent}' requires human")
        return state

    # Rule 3 — Customer not found
    if state.customer is None:
        state.should_escalate = True
        state.escalation_reason = f"Customer '{state.customer_id}' not found in system"
        state.confidence = 0.0
        state.add_trace("Decision: escalate — customer not found")
        return state

    # Rule 4 — Suspended account
    if state.customer.get("status") == "suspended":
        state.should_escalate = True
        state.escalation_reason = "Customer account is suspended"
        state.confidence = 0.0
        state.add_trace("Decision: escalate — account suspended")
        return state

    # Rule 5 — No KB results for doc-dependent intents
    doc_dependent = {
        "sso_setup", "csv_export_issue", "webhook_issue",
        "plan_limits", "general_question",
    }
    if state.intent in doc_dependent and len(state.kb_results) < MIN_KB_RESULTS:
        state.should_escalate = True
        state.escalation_reason = "No relevant documentation found to resolve this query"
        state.confidence = 0.2
        state.add_trace("Decision: escalate — no KB results found")
        return state


    # Rule 6 — Active incident (inform, don't escalate unless no KB)
    if state.incidents:
        state.add_trace(
            f"Decision: active incident found ({state.incidents[0]['incident_id']}) — informing customer"
        )

    # ── Compute confidence ────────────────────────────────────────
    confidence = _compute_confidence(state)
    state.confidence = confidence

    # Rule 7 — Low confidence
    if confidence < settings_min_confidence():
        state.should_escalate = True
        state.escalation_reason = f"Confidence too low to auto-resolve ({confidence:.2f})"
        state.add_trace(f"Decision: escalate — confidence {confidence:.2f} below threshold")
        return state

    # Rule 8 — Auto-resolve
    state.should_escalate = False
    state.escalation_reason = None
    state.add_trace(f"Decision: auto-resolve — confidence {confidence:.2f}")
    return state


def _compute_confidence(state: AgentState) -> float:
    """
    Computes resolution confidence based on available evidence.
    """
    score = 0.5  # base

    # KB results boost confidence
    if state.kb_results:
        top_score = state.kb_results[0].get("rerank_score", 0)
        # Normalize rerank score (cross-encoder logits) to 0-1 range
        normalized = min(max((top_score + 5) / 15, 0.0), 1.0)
        score += 0.3 * normalized

    # Customer data available
    if state.customer:
        score += 0.1

    # Diagnostics available and healthy
    if state.diagnostics:
        checks = state.diagnostics.get("checks", [])
        ok_count = sum(1 for c in checks if c["status"] == "ok")
        score += 0.05 * (ok_count / max(len(checks), 1))

    # Intent confidence from classifier
    score += 0.1 * state.intent_confidence

    return round(min(score, 1.0), 3)


def settings_min_confidence() -> float:
    """Import here to avoid circular imports."""
    from src.config import settings
    return settings.agent_min_confidence


if __name__ == "__main__":
    from src.agent.state import AgentState

    print("[decision] Test 1 - billing refund (always escalate):")
    state = AgentState(customer_id="cust_1001", query="Refund my invoice")
    state.intent = "billing_refund"
    state.customer = {"status": "active", "plan": "business"}
    result = evaluate(state)
    print(f"  escalate={result.should_escalate} reason={result.escalation_reason}")

    print("\n[decision] Test 2 - normal query with KB results:")
    state2 = AgentState(customer_id="cust_1001", query="How do I set up SSO?")
    state2.intent = "sso_setup"
    state2.intent_confidence = 0.95
    state2.customer = {"status": "active", "plan": "enterprise"}
    state2.kb_results = [{"rerank_score": 5.1, "source_file": "sso-setup-v3.md", "section": "Overview"}]
    result2 = evaluate(state2)
    print(f"  escalate={result2.should_escalate} confidence={result2.confidence}")

    print("\n[decision] Test 3 - suspended account:")
    state3 = AgentState(customer_id="cust_9999", query="Help me with export")
    state3.intent = "csv_export_issue"
    state3.customer = {"status": "suspended", "plan": "starter"}
    result3 = evaluate(state3)
    print(f"  escalate={result3.should_escalate} reason={result3.escalation_reason}")