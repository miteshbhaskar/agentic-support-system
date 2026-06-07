"""src/api/routes/knowledge_base.py"""

from fastapi import APIRouter, Query
from typing import Optional
from src.api.db import fetchall
from src.models.schemas import KBDocument

router = APIRouter(prefix="/knowledge-base", tags=["knowledge-base"])


@router.get("/search", response_model=list[KBDocument])
async def search_knowledge_base(
    q: Optional[str] = Query(None, description="Keyword search"),
    category: Optional[str] = Query(None),
    version: Optional[str] = Query(None, description="e.g. 2.x, 3.x, 3.1, 3.2"),
    exclude_adversarial: bool = Query(True),
):
    sql = "SELECT * FROM kb_documents WHERE 1=1"
    params: list = []

    if exclude_adversarial:
        sql += " AND is_adversarial = 0"

    if q:
        sql += " AND (LOWER(title) LIKE ? OR LOWER(content) LIKE ? OR LOWER(section) LIKE ?)"
        kw = f"%{q.lower()}%"
        params.extend([kw, kw, kw])

    if category:
        sql += " AND category = ?"
        params.append(category.lower())

    if version:
        # Match exact version OR 'all', handle major version grouping
        major = version.split(".")[0] + ".x"
        sql += " AND (product_version = ? OR product_version = ? OR product_version = 'all')"
        params.extend([version, major])

    rows = await fetchall(sql, tuple(params))
    return [
        {**r, "is_adversarial": bool(r["is_adversarial"])} for r in rows
    ]
