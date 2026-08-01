from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock


TERMINAL_STATUSES = {"succeeded", "failed", "awaiting_user", "cancelled", "closed"}


class LocalStateStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def _initialize(self) -> None:
        with self._lock, self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS runtime_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS assignments (
                    kind TEXT NOT NULL,
                    assignment_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    local_status TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (kind, assignment_id)
                );
                CREATE TABLE IF NOT EXISTS outbox (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    method TEXT NOT NULL,
                    path TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    assignment_kind TEXT,
                    assignment_id TEXT,
                    terminal INTEGER NOT NULL DEFAULT 0,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    created_at TEXT NOT NULL
                );
                """
            )

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def get_value(self, key: str) -> str | None:
        with self._lock, self._connect() as db:
            row = db.execute("SELECT value FROM runtime_state WHERE key = ?", (key,)).fetchone()
            return str(row["value"]) if row else None

    def set_value(self, key: str, value: str) -> None:
        with self._lock, self._connect() as db:
            db.execute(
                """
                INSERT INTO runtime_state(key, value, updated_at) VALUES(?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                """,
                (key, value, self._now()),
            )

    def save_assignment(self, kind: str, assignment_id: str, payload: dict) -> None:
        with self._lock, self._connect() as db:
            db.execute(
                """
                INSERT INTO assignments(kind, assignment_id, payload_json, local_status, updated_at)
                VALUES(?, ?, ?, 'claimed', ?)
                ON CONFLICT(kind, assignment_id) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (kind, assignment_id, json.dumps(payload, ensure_ascii=False), self._now()),
            )

    def update_assignment_status(self, kind: str, assignment_id: str, status: str) -> None:
        with self._lock, self._connect() as db:
            db.execute(
                "UPDATE assignments SET local_status = ?, updated_at = ? WHERE kind = ? AND assignment_id = ?",
                (status, self._now(), kind, assignment_id),
            )

    def resumable_assignment(self, kind: str) -> dict | None:
        with self._lock, self._connect() as db:
            row = db.execute(
                """
                SELECT payload_json FROM assignments
                WHERE kind = ? AND local_status IN ('claimed', 'running')
                ORDER BY updated_at LIMIT 1
                """,
                (kind,),
            ).fetchone()
            return json.loads(row["payload_json"]) if row else None

    def delete_assignment(self, kind: str, assignment_id: str) -> None:
        with self._lock, self._connect() as db:
            db.execute(
                "DELETE FROM assignments WHERE kind = ? AND assignment_id = ?",
                (kind, assignment_id),
            )

    def enqueue(
        self,
        *,
        method: str,
        path: str,
        payload: dict,
        assignment_kind: str | None = None,
        assignment_id: str | None = None,
        terminal: bool = False,
    ) -> int:
        with self._lock, self._connect() as db:
            cursor = db.execute(
                """
                INSERT INTO outbox(
                    method, path, payload_json, assignment_kind, assignment_id,
                    terminal, created_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    method,
                    path,
                    json.dumps(payload, ensure_ascii=False),
                    assignment_kind,
                    assignment_id,
                    1 if terminal else 0,
                    self._now(),
                ),
            )
            return int(cursor.lastrowid)

    def pending_outbox(self, limit: int = 100) -> list[dict]:
        with self._lock, self._connect() as db:
            rows = db.execute(
                "SELECT * FROM outbox ORDER BY id LIMIT ?",
                (limit,),
            ).fetchall()
            return [
                {
                    **dict(row),
                    "payload": json.loads(row["payload_json"]),
                }
                for row in rows
            ]

    def mark_outbox_failure(self, outbox_id: int, error: str) -> None:
        with self._lock, self._connect() as db:
            db.execute(
                "UPDATE outbox SET attempts = attempts + 1, last_error = ? WHERE id = ?",
                (error[:1000], outbox_id),
            )

    def delete_outbox(self, outbox_id: int) -> None:
        with self._lock, self._connect() as db:
            db.execute("DELETE FROM outbox WHERE id = ?", (outbox_id,))

    def outbox_count(self) -> int:
        with self._lock, self._connect() as db:
            return int(db.execute("SELECT COUNT(*) FROM outbox").fetchone()[0])
