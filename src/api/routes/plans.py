"""src/api/routes/plans.py"""

from fastapi import APIRouter, HTTPException
from src.api.db import fetchone, fetchall, parse_json_fields
from src.models.schemas import PlanResponse

router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("/{plan_name}", response_model=PlanResponse)
async def get_plan(plan_name: str):
    row = await fetchone(
        "SELECT * FROM plans WHERE plan_name = ?", (plan_name.lower(),)
    )
    if not row:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_name}' not found")
    return parse_json_fields(row, ["features", "limits", "restrictions"])


@router.get("/", response_model=list[PlanResponse])
async def list_plans():
    rows = await fetchall("SELECT * FROM plans")
    return [parse_json_fields(r, ["features", "limits", "restrictions"]) for r in rows]
