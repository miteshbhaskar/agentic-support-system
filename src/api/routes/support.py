"""
src/api/routes/support.py
─────────────────────────
POST /support/query — main entry point for the agentic support system.
"""

import logging
from fastapi import APIRouter, HTTPException
from src.models.schemas import SupportQueryRequest, SupportQueryResponse
from src.agent.orchestrator import run_agent

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/support", tags=["support"])


@router.post("/query", response_model=SupportQueryResponse)
async def support_query(req: SupportQueryRequest):
    """
    Main agentic support endpoint.
    Receives customer_id + query, runs full orchestration workflow,
    returns structured resolution with citations and execution trace.
    """
    if not req.customer_id or not req.customer_id.strip():
        raise HTTPException(status_code=400, detail="customer_id is required")
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="query is required")

    logger.info(f"Support query received: customer={req.customer_id} query={req.query[:80]}")

    response = await run_agent(
        customer_id=req.customer_id.strip(),
        query=req.query.strip(),
    )

    logger.info(
        f"Support query resolved: customer={req.customer_id} "
        f"status={response.status} confidence={response.confidence} "
        f"escalated={response.escalation_required}"
    )

    return response