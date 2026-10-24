#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LLM 响应缓存（SQLite）

回测重跑时，同一输入直接命中缓存，保证数值可复现并节省成本。
"""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
from typing import Optional

logger = logging.getLogger(__name__)

DB_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "llm_cache.sqlite")
)
_LOCK = threading.Lock()


class ResponseCache:
    """按输入 hash 缓存 LLM 响应"""

    def __init__(self, path: Optional[str] = None):
        self.path = path or DB_PATH
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with _LOCK, self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS llm_cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=10)

    def get(self, key: str) -> Optional[str]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM llm_cache WHERE key = ?", (key,)
            ).fetchone()
        return row[0] if row else None

    def set(self, key: str, value: str) -> None:
        with _LOCK, self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO llm_cache (key, value) VALUES (?, ?)",
                (key, value),
            )
            conn.commit()

    def count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) FROM llm_cache").fetchone()
        return int(row[0]) if row else 0
