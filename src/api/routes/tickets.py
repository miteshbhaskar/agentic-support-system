"""src/api/routes/tickets.py"""

import json
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from src.api.db import fetchone, execute, parse_json_fields
from src.models.schemas import TicketCreateRequest, TicketResponse

router = APIRouter(prefix="/tickets", tags=["tickets"])


def _generate_ticket_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")[:17]
    return f"TKT-{ts}"


@router.post("/", response_model=TicketResponse, status_code=201)
async def create_ticket(req: TicketCreateRequest):
    # Idempotency check
    if req.idempotency_key:
        existing = await fetchone(
            "SELECT * FROM tickets WHERE idempotency_key = ?",
            (req.idempotency_key,),
        )
        if existing:
            return parse_json_fields(existing, ["evidence"])

    # Verify customer exists
    customer = await fetchone(
        "SELECT customer_id FROM customers WHERE customer_id = ?",
        (req.customer_id,),
    )
    if not customer:
        raise HTTPException(status_code=404, detail=f"Customer '{req.customer_id}' not found")

    ticket_id = _generate_ticket_id()
    now = datetime.now(timezone.utc).isoformat()
    evidence_json = json.dumps(req.evidence)

    await execute(
        """INSERT INTO tickets
           (ticket_id, customer_id, category, priority, summary, evidence,
            status, assigned_team, created_at, idempotency_key)
           VALUES (?, ?, ?, ?, ?, ?, 'created', ?, ?, ?)""",
        (
            ticket_id,
            req.customer_id,
            req.category,
            req.priority,
            req.summary,
            evidence_json,
            req.assigned_team,
            now,
            req.idempotency_key,
        ),
    )

    row = await fetchone("SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,))
    return parse_json_fields(row, ["evidence"])


@router.get("/{ticket_id}", response_model=TicketResponse)
async def get_ticket(ticket_id: str):
    row = await fetchone(
        "SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,)
    )
    if not row:
        raise HTTPException(status_code=404, detail=f"Ticket '{ticket_id}' not found")
    return parse_json_fields(row, ["evidence"])
