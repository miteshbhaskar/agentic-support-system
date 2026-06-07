"""src/api/db.py — SQLite async connection and helpers."""

import json
import sqlite3
import aiosqlite
from contextlib import asynccontextmanager
from typing import Any
from src.config import settings


def parse_json_fields(row: dict, fields: list[str]) -> dict:
    """Deserialize TEXT-stored JSON fields into Python dicts/lists."""
    for field in fields:
        if field in row and isinstance(row[field], str):
            try:
                row[field] = json.loads(row[field])
            except (json.JSONDecodeError, TypeError):
                pass
    return row


@asynccontextmanager
async def get_db():
    """Async context manager for SQLite connection."""
    async with aiosqlite.connect(settings.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        yield conn


async def fetchone(query: str, params: tuple = ()) -> dict | None:
    async with get_db() as conn:
        async with conn.execute(query, params) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def fetchall(query: str, params: tuple = ()) -> list[dict]:
    async with get_db() as conn:
        async with conn.execute(query, params) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def execute(query: str, params: tuple = ()) -> int:
    """Execute INSERT/UPDATE/DELETE. Returns lastrowid."""
    async with get_db() as conn:
        async with conn.execute(query, params) as cur:
            await conn.commit()
            return cur.lastrowid
