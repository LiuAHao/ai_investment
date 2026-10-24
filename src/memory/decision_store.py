#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
决策记录存储（SQLite）

表：
- decisions：每次研究的裁决与结算（payload 存完整 JSON）
- traces：每次任务的阶段耗时与调用量

设计：标准库 sqlite3，不引入 ORM；写入幂等（decision_id 主键）。
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DB_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "decisions.sqlite")
)

_LOCK = threading.Lock()


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _LOCK, _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS decisions (
                decision_id TEXT PRIMARY KEY,
                session_id TEXT,
                query TEXT,
                asset_ids TEXT,
                as_of TEXT,
                horizon TEXT,
                stance TEXT,
                conviction REAL,
                evidence_count INTEGER,
                payload TEXT,
                settlement TEXT,
                reflection TEXT,
                created_at TEXT,
                settled_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS traces (
                task_id TEXT PRIMARY KEY,
                payload TEXT,
                created_at TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_decisions_created ON decisions(created_at)")
        conn.commit()


def save_decision(record: Dict[str, Any]) -> str:
    """写入决策记录（幂等）"""
    init_db()
    decision_id = str(record.get("decision_id") or "")
    if not decision_id:
        raise ValueError("decision_id 不能为空")
    asset_ids = record.get("asset_ids") or []
    with _LOCK, _connect() as conn:
        conn.execute(
            """
            INSERT INTO decisions (
                decision_id, session_id, query, asset_ids, as_of, horizon,
                stance, conviction, evidence_count, payload, settlement, reflection, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(decision_id) DO UPDATE SET
                payload=excluded.payload,
                stance=excluded.stance,
                conviction=excluded.conviction,
                evidence_count=excluded.evidence_count
            """,
            (
                decision_id,
                str(record.get("session_id") or ""),
                str(record.get("query") or ""),
                json.dumps(asset_ids, ensure_ascii=False),
                str(record.get("as_of") or ""),
                str(record.get("horizon") or ""),
                str(record.get("stance") or ""),
                float(record.get("conviction") or 0.0),
                int(record.get("evidence_count") or 0),
                json.dumps(record.get("payload") or {}, ensure_ascii=False, default=str),
                json.dumps(record.get("settlement"), ensure_ascii=False) if record.get("settlement") else None,
                record.get("reflection"),
                str(record.get("created_at") or datetime.now().isoformat(timespec="seconds")),
            ),
        )
        conn.commit()
    return decision_id


def get_decision(decision_id: str) -> Optional[Dict[str, Any]]:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM decisions WHERE decision_id = ?", (decision_id,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def list_unsettled(limit: int = 50) -> List[Dict[str, Any]]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM decisions WHERE settlement IS NULL ORDER BY created_at ASC LIMIT ?",
            (limit,),
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def list_recent(asset_id: Optional[str] = None, limit: int = 8) -> List[Dict[str, Any]]:
    init_db()
    with _connect() as conn:
        if asset_id:
            rows = conn.execute(
                "SELECT * FROM decisions WHERE asset_ids LIKE ? ORDER BY created_at DESC LIMIT ?",
                (f"%{asset_id}%", limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM decisions ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
    return [_row_to_dict(row) for row in rows]


def update_settlement(
    decision_id: str,
    settlement: Dict[str, Any],
    reflection: Optional[str] = None,
) -> None:
    init_db()
    with _LOCK, _connect() as conn:
        conn.execute(
            "UPDATE decisions SET settlement = ?, reflection = ?, settled_at = ? WHERE decision_id = ?",
            (
                json.dumps(settlement, ensure_ascii=False),
                reflection,
                datetime.now().isoformat(timespec="seconds"),
                decision_id,
            ),
        )
        conn.commit()


def save_trace(task_id: str, trace: Dict[str, Any]) -> None:
    init_db()
    with _LOCK, _connect() as conn:
        conn.execute(
            """
            INSERT INTO traces (task_id, payload, created_at) VALUES (?, ?, ?)
            ON CONFLICT(task_id) DO UPDATE SET payload=excluded.payload
            """,
            (
                task_id,
                json.dumps(trace, ensure_ascii=False, default=str),
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        conn.commit()


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    data = dict(row)
    for key in ("asset_ids", "payload", "settlement"):
        raw = data.get(key)
        if isinstance(raw, str) and raw:
            try:
                data[key] = json.loads(raw)
            except json.JSONDecodeError:
                data[key] = {} if key != "asset_ids" else []
    return data
