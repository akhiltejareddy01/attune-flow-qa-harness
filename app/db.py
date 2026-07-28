"""
Tiny storage layer. One SQLite file, one table.

Each "run" (a full batch of graded calls) is saved as a row: an id, a
timestamp, and the whole result as JSON. That's all the dashboard needs.
"""

import os
import json
import sqlite3
from datetime import datetime
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "flowqa.db")


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                data TEXT NOT NULL
            )
            """
        )


def save_run(data: dict) -> int:
    """Save one batch. Returns the new run id."""
    created_at = datetime.utcnow().isoformat()
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO runs (created_at, data) VALUES (?, ?)",
            (created_at, json.dumps(data)),
        )
        return cur.lastrowid


def get_latest_run() -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, created_at, data FROM runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
    if not row:
        return None
    data = json.loads(row["data"])
    data["run_id"] = row["id"]
    data["created_at"] = row["created_at"]
    return data


def get_run(run_id: int) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, created_at, data FROM runs WHERE id = ?", (run_id,)
        ).fetchone()
    if not row:
        return None
    data = json.loads(row["data"])
    data["run_id"] = row["id"]
    data["created_at"] = row["created_at"]
    return data