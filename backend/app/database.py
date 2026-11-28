"""Async SQLite helpers using aiosqlite."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiosqlite

from app.config import get_settings

CREATE_MESSAGES_TABLE = """
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  metadata TEXT,
  created_at TEXT NOT NULL
);
"""

CREATE_SESSION_INDEX = """
CREATE INDEX IF NOT EXISTS idx_session_id ON messages(session_id);
"""


def _db_path() -> str:
    settings = get_settings()
    path = settings.db_path
    # Ensure the directory exists
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    return path


async def check_db() -> bool:
    """Verify the SQLite database is reachable."""
    async with aiosqlite.connect(_db_path()) as db:
        await db.execute("SELECT 1")
    return True


async def init_db() -> None:
    """Initialize the SQLite database (create tables if they don't exist)."""
    async with aiosqlite.connect(_db_path()) as db:
        await db.execute(CREATE_MESSAGES_TABLE)
        await db.execute(CREATE_SESSION_INDEX)
        await db.commit()


def _message_from_row(row: aiosqlite.Row) -> Dict[str, Any]:
    item: Dict[str, Any] = {
        "id": row["id"],
        "role": row["role"],
        "content": row["content"],
    }
    if row["metadata"]:
        item["metadata"] = json.loads(row["metadata"])
    return item


async def get_session_messages(
    session_id: str, limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Return session messages in chronological order, optionally bounded to the latest rows."""
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        if limit is None:
            cursor = await db.execute(
                "SELECT id, role, content, metadata FROM messages WHERE session_id = ? ORDER BY id ASC",
                (session_id,),
            )
        else:
            cursor = await db.execute(
                "SELECT id, role, content, metadata FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                (session_id, limit),
            )
        async with cursor:
            rows = await cursor.fetchall()
    if limit is not None:
        rows.reverse()
    return [_message_from_row(row) for row in rows]


async def get_session_message_page(
    session_id: str, before_id: Optional[int] = None, limit: int = 100
) -> tuple[List[Dict[str, Any]], Optional[int]]:
    """Return the latest page before a stable message cursor and the next older cursor."""
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        if before_id is None:
            cursor = await db.execute(
                "SELECT id, role, content, metadata FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                (session_id, limit + 1),
            )
        else:
            cursor = await db.execute(
                "SELECT id, role, content, metadata FROM messages WHERE session_id = ? AND id < ? ORDER BY id DESC LIMIT ?",
                (session_id, before_id, limit + 1),
            )
        async with cursor:
            rows = await cursor.fetchall()

    has_more = len(rows) > limit
    page = rows[:limit]
    next_before_id = page[-1]["id"] if has_more else None
    page.reverse()
    return [_message_from_row(row) for row in page], next_before_id


async def delete_session_messages(session_id: str) -> bool:
    """Delete all stored messages for a session. Return whether it existed."""
    async with aiosqlite.connect(_db_path()) as db:
        async with db.execute(
            "DELETE FROM messages WHERE session_id = ?",
            (session_id,),
        ) as cursor:
            deleted = cursor.rowcount > 0
        await db.commit()
    return deleted


async def save_messages(
    session_id: str,
    user_content: str,
    assistant_content: str,
    assistant_metadata: Dict[str, Any],
) -> None:
    """Persist the user message and assistant reply to the database."""
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(_db_path()) as db:
        await db.execute(
            "INSERT INTO messages (session_id, role, content, metadata, created_at) VALUES (?, ?, ?, ?, ?)",
            (session_id, "user", user_content, None, now),
        )
        await db.execute(
            "INSERT INTO messages (session_id, role, content, metadata, created_at) VALUES (?, ?, ?, ?, ?)",
            (
                session_id,
                "assistant",
                assistant_content,
                json.dumps(assistant_metadata),
                now,
            ),
        )
        await db.commit()
