from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any


class OriginalStore:
    """SQLite-backed local store for raw context payloads."""

    def __init__(self, db_path: str | Path = ".cbm/context.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        conn = self._connect()
        try:
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS originals (
                        handle TEXT PRIMARY KEY,
                        sha256 TEXT NOT NULL,
                        content_type TEXT NOT NULL,
                        source_name TEXT,
                        created_at REAL NOT NULL,
                        original_text TEXT NOT NULL,
                        metadata_json TEXT NOT NULL
                    )
                    """
                )
                conn.execute("CREATE INDEX IF NOT EXISTS idx_originals_sha ON originals(sha256)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_originals_created ON originals(created_at)")
        finally:
            conn.close()

    def put(
        self,
        original_text: str,
        content_type: str,
        source_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        digest = hashlib.sha256(original_text.encode("utf-8")).hexdigest()
        handle = f"ctx_{uuid.uuid4().hex[:12]}"
        payload = json.dumps(metadata or {}, sort_keys=True)

        conn = self._connect()
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO originals(handle, sha256, content_type, source_name, created_at, original_text, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (handle, digest, content_type, source_name, time.time(), original_text, payload),
                )
        finally:
            conn.close()
        return handle

    def get(self, handle: str) -> str:
        conn = self._connect()
        try:
            with conn:
                row = conn.execute(
                    "SELECT original_text FROM originals WHERE handle = ?",
                    (handle,),
                ).fetchone()
        finally:
            conn.close()
        if row is None:
            raise KeyError(f"No context found for handle: {handle}")
        return str(row[0])

    def stats(self) -> dict[str, Any]:
        conn = self._connect()
        try:
            with conn:
                total = conn.execute("SELECT COUNT(*) FROM originals").fetchone()[0]
                by_type = conn.execute(
                    "SELECT content_type, COUNT(*) FROM originals GROUP BY content_type ORDER BY COUNT(*) DESC"
                ).fetchall()
        finally:
            conn.close()
        return {"total_originals": total, "by_type": dict(by_type), "db_path": str(self.db_path)}

    def prune(self, max_age_seconds: float) -> int:
        cutoff = time.time() - max_age_seconds
        conn = self._connect()
        try:
            with conn:
                cursor = conn.execute("DELETE FROM originals WHERE created_at < ?", (cutoff,))
                deleted = cursor.rowcount
            # VACUUM outside transaction context
            conn.execute("VACUUM")
        finally:
            conn.close()
        return deleted

