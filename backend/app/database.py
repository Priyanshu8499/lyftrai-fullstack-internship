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


async def get_session_messages(session_id: str) -> List[Dict[str, Any]]:
    """Return all messages for a session ordered by creation time."""
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT role, content, metadata FROM messages WHERE session_id = ? ORDER BY id ASC",
            (session_id,),
        ) as cursor:
            rows = await cursor.fetchall()
    result = []
    for row in rows:
        item: Dict[str, Any] = {"role": row["role"], "content": row["content"]}
        if row["metadata"]:
            item["metadata"] = json.loads(row["metadata"])
        result.append(item)
    return result


async def session_exists(session_id: str) -> bool:
    """Return True if the session has at least one message in the DB."""
    async with aiosqlite.connect(_db_path()) as db:
        async with db.execute(
            "SELECT 1 FROM messages WHERE session_id = ? LIMIT 1",
            (session_id,),
        ) as cursor:
            row = await cursor.fetchone()
    return row is not None


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
