"""src/models/schemas.py — Shared Pydantic models for API and agent."""

from pydantic import BaseModel, Field
from typing import Any, Optional


# ── Customer ──────────────────────────────────────────────────────
class CustomerResponse(BaseModel):
    customer_id: str
    company_name: str
    plan: str
    product_version: str
    region: str
    features: dict[str, Any]
    limits: dict[str, Any]
    created_at: str
    status: str


# ── Plan ──────────────────────────────────────────────────────────
class PlanResponse(BaseModel):
    plan_name: str
    display_name: str
    features: dict[str, Any]
    limits: dict[str, Any]
    restrictions: dict[str, Any]


# ── Incident ──────────────────────────────────────────────────────
class IncidentResponse(BaseModel):
    incident_id: str
    service: str
    region: str
    status: str
    severity: str
    title: str
    description: str
    started_at: str
    resolved_at: Optional[str] = None
    affects_plans: Optional[list[str]] = None


# ── Ticket ────────────────────────────────────────────────────────
class TicketCreateRequest(BaseModel):
    customer_id: str
    category: str
    priority: str = "medium"
    summary: str
    evidence: list[str] = Field(default_factory=list)
    assigned_team: str = "support"
    idempotency_key: Optional[str] = None


class TicketResponse(BaseModel):
    ticket_id: str
    customer_id: str
    category: str
    priority: str
    summary: str
    evidence: list[str]
    status: str
    assigned_team: str
    created_at: str
    idempotency_key: Optional[str] = None


# ── Knowledge Base ────────────────────────────────────────────────
class KBDocument(BaseModel):
    doc_id: str
    title: str
    source_file: str
    category: str
    product_version: str
    section: str
    content: str
    is_adversarial: bool


# ── Diagnostics ───────────────────────────────────────────────────
class DiagnosticResult(BaseModel):
    check: str
    status: str
    latency_ms: int
    detail: Optional[str] = None


class DiagnosticsResponse(BaseModel):
    customer_id: str
    checks: list[DiagnosticResult]


# ── Support Query (Part 5) ────────────────────────────────────────
class SupportQueryRequest(BaseModel):
    customer_id: str
    query: str


class ToolUsed(BaseModel):
    tool: str
    status: str
    latency_ms: Optional[int] = None
    citations: Optional[list[str]] = None


class Citation(BaseModel):
    source: str
    section: str
    relevance: float


class SupportQueryResponse(BaseModel):
    ticket_id: Optional[str] = None
    customer_id: str
    status: str
    answer: str
    confidence: float
    escalation_required: bool
    escalation_reason: Optional[str] = None
    tools_used: list[ToolUsed] = Field(default_factory=list)
    execution_trace: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)


# ── Error ─────────────────────────────────────────────────────────
class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
