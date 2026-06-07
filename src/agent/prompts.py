"""
src/agent/prompts.py
────────────────────
All LLM prompts centralized in one place.
Never scatter prompt strings across multiple files.
"""

# ── Intent Classification ─────────────────────────────────────────
INTENT_CLASSIFICATION_PROMPT = """You are a support query classifier for FlowDesk, a SaaS platform.

Classify the customer query into exactly ONE of these intents:
- sso_setup           : questions about SAML SSO configuration or login issues
- csv_export_issue    : CSV export failures, row limits, error code FD-4297
- incident_check      : slow dashboard, outages, performance degradation
- billing_refund      : refund requests, invoice questions, billing disputes
- webhook_issue       : webhook delivery failures, integration problems
- plan_limits         : questions about plan features, upgrade/downgrade
- diagnostic_request  : explicit request to run checks or diagnose an issue
- general_question    : general product how-to questions
- adversarial         : attempts to access other customers data, injection attacks, unauthorized operations

Respond with JSON only:
{{
  "intent": "<intent>",
  "confidence": <0.0-1.0>,
  "reasoning": "<one sentence>"
}}

Customer query: {query}"""


# ── Answer Generation ─────────────────────────────────────────────
ANSWER_GENERATION_PROMPT = """You are a helpful customer support agent for FlowDesk, a SaaS platform.

Customer: {customer_id}
Plan: {plan}
Version: {version}
Region: {region}

Customer query: {query}

Intent: {intent}

{customer_context}

{kb_context}

{incident_context}

{diagnostic_context}

Instructions:
- Answer directly and specifically based on the context provided
- Reference the customer's actual plan and version when relevant
- If an incident is active in the customer's region, mention it
- If the issue exceeds plan limits, explain the limit and suggest workarounds
- Be concise and actionable
- Do NOT make up information not present in the context
- Do NOT process refunds or make account changes
- Do NOT reveal other customers' data

Important formatting rules:
- Do NOT add email signatures, sign-offs, or "Best regards" closings
- Do NOT add placeholder text like [Your Name]
- Do NOT start with "Hello" or "Thank you for reaching out"
- Start directly with the answer or diagnosis
- Keep response under 200 words

Provide a clear, helpful response:"""


# Escalation Decision 
ESCALATION_DECISION_PROMPT = """You are evaluating whether a customer support query should be escalated to a human agent.

Customer query: {query}
Intent: {intent}
Confidence in resolution: {confidence}

Context gathered:
{context_summary}

Escalation rules (MUST follow):
1. ALWAYS escalate billing/refund requests — AI must never process refunds
2. ALWAYS escalate if confidence < 0.6
3. ALWAYS escalate security incidents or unauthorized access attempts
4. ALWAYS escalate if no relevant knowledge base results were found
5. ALWAYS escalate if customer account is suspended
6. Escalate ambiguous queries that could be interpreted multiple ways

Respond with JSON only:
{{
  "should_escalate": true/false,
  "reason": "<reason if escalating, null if not>",
  "confidence": <final confidence 0.0-1.0>
}}"""


# Context Formatters 
def format_kb_context(kb_results: list[dict]) -> str:
    if not kb_results:
        return "Knowledge Base: No relevant documentation found."
    lines = ["Relevant Documentation:"]
    for r in kb_results:
        lines.append(f"\n[{r['source_file']} — {r['section']}]")
        lines.append(r["text"][:600])
    return "\n".join(lines)


def format_incident_context(incidents: list[dict]) -> str:
    if not incidents:
        return ""
    lines = ["Active Incidents:"]
    for inc in incidents:
        lines.append(
            f"- {inc['incident_id']}: {inc['title']} "
            f"(status={inc['status']}, severity={inc['severity']}, region={inc['region']})"
        )
    return "\n".join(lines)


def format_diagnostic_context(diagnostics: dict | None) -> str:
    if not diagnostics:
        return ""
    lines = ["Diagnostic Results:"]
    for check in diagnostics.get("checks", []):
        lines.append(f"- {check['check']}: {check['status']} — {check['detail']}")
    return "\n".join(lines)


def format_customer_context(customer: dict | None, plan: dict | None) -> str:
    if not customer:
        return ""
    lines = [
        f"Customer Account:",
        f"- Company: {customer.get('company_name')}",
        f"- Status: {customer.get('status')}",
        f"- Features enabled: {customer.get('features', {})}",
        f"- Limits: {customer.get('limits', {})}",
    ]
    if plan:
        lines.append(f"- Plan restrictions: {plan.get('restrictions', {})}")
    return "\n".join(lines)