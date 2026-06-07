"""src/api/routes/customers.py"""

from fastapi import APIRouter, HTTPException
from src.api.db import fetchone
from src.models.schemas import CustomerResponse
from src.api.db import parse_json_fields

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(customer_id: str):
    row = await fetchone(
        "SELECT * FROM customers WHERE customer_id = ?", (customer_id,)
    )
    if not row:
        raise HTTPException(status_code=404, detail=f"Customer '{customer_id}' not found")
    return parse_json_fields(row, ["features", "limits"])
