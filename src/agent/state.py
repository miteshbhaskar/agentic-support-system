"""
src/agent/state.py
──────────────────
Workflow state model for the LangGraph orchestrator.
Carries all data across nodes — input, intermediate results, and final output.
"""

from typing import Any, Optional
from pydantic import BaseModel, Field


class AgentState(BaseModel):
    """
    Single state object passed between all LangGraph nodes.
    Each node reads what it needs and writes its results back.
    """

    # Input 
    customer_id: str
    query: str

    # Security 
    threat_level: str = "none"          # none / medium / high
    injection_detected: bool = False
    unauthorized_access: bool = False

    # Intent 
    intent: str = ""                    # classified intent
    intent_confidence: float = 0.0

    # Customer context 
    customer: Optional[dict] = None     # full customer record
    plan: Optional[dict] = None         # plan details

    # Tool results 
    kb_results: list[dict] = Field(default_factory=list)
    incidents: list[dict] = Field(default_factory=list)
    diagnostics: Optional[dict] = None

    # Tool trace 
    tools_used: list[dict] = Field(default_factory=list)

    # Decision
    should_escalate: bool = False
    escalation_reason: Optional[str] = None
    confidence: float = 0.0

    # Output 
    answer: str = ""
    ticket_id: Optional[str] = None
    citations: list[dict] = Field(default_factory=list)
    execution_trace: list[str] = Field(default_factory=list)
    status: str = "pending"             # pending / resolved / escalated / rejected

    # Error tracking
    errors: list[str] = Field(default_factory=list)

    def add_trace(self, message: str) -> None:
        """Append a step to the execution trace."""
        self.execution_trace.append(message)

    def add_tool(self, tool: str, status: str, latency_ms: int = 0, citations: list = None) -> None:
        """Record a tool call in the trace."""
        entry = {"tool": tool, "status": status, "latency_ms": latency_ms}
        if citations:
            entry["citations"] = citations
        self.tools_used.append(entry)

    def add_error(self, error: str) -> None:
        self.errors.append(error)

    class Config:
        arbitrary_types_allowed = True