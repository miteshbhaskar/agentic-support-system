"""src/api/routes/incidents.py"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from src.api.db import fetchone, fetchall, parse_json_fields
from src.models.schemas import IncidentResponse

router = APIRouter(prefix="/incidents", tags=["incidents"])

ACTIVE_STATUSES = ("investigating", "identified", "monitoring")


@router.get("/", response_model=list[IncidentResponse])
async def list_incidents(
    region: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    active_only: bool = Query(False),
):
    query = "SELECT * FROM incidents WHERE 1=1"
    params: list = []

    if region:
        query += " AND (region = ? OR region = 'global')"
        params.append(region)

    if active_only:
        placeholders = ",".join("?" * len(ACTIVE_STATUSES))
        query += f" AND status IN ({placeholders})"
        params.extend(ACTIVE_STATUSES)
    elif status:
        query += " AND status = ?"
        params.append(status)

    query += " ORDER BY started_at DESC"
    rows = await fetchall(query, tuple(params))
    return [parse_json_fields(r, ["affects_plans"]) for r in rows]


@router.get("/{incident_id}", response_model=IncidentResponse)
async def get_incident(incident_id: str):
    row = await fetchone(
        "SELECT * FROM incidents WHERE incident_id = ?", (incident_id,)
    )
    if not row:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found")
    return parse_json_fields(row, ["affects_plans"])
