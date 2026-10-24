#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""可观测性存储：任务运行、事件、LLM 调用、工具调用的 SQLite 留痕。

写入走异步队列 + 批量事务，绝不让埋点阻塞或中断业务。
"""

from __future__ import annotations

import json
import os
import queue
import re
import shutil
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

DEFAULT_DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "observability.sqlite")
MAX_PAYLOAD_CHARS = 4096

RUN_FIELDS = {
    "session_id", "query", "source", "status", "started_at", "finished_at",
    "duration_ms", "model", "plan_json", "verdict_stance", "conviction",
    "evidence_count", "llm_calls", "tool_calls", "error_type", "error",
    "decision_id", "degraded", "trace_json",
}

_SECRET_KEYS = re.compile(r"(api[_-]?key|token|secret|password|authorization|apca-api)", re.IGNORECASE)


def now_iso() -> str:
    return datetime.now().isoformat(timespec="milliseconds")


def redact(value: Any) -> Any:
    """递归脱敏。只处理 dict/list，其余原样返回。"""
    if isinstance(value, dict):
        return {
            key: ("***" if _SECRET_KEYS.search(str(key)) else redact(item))
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    return value


def truncate(text: Any, limit: int = MAX_PAYLOAD_CHARS) -> str:
    if text is None:
        return ""
    if not isinstance(text, str):
        text = json.dumps(text, ensure_ascii=False, default=str)
    return text[:limit]


def classify_error(error: Any) -> str:
    """把异常归类，便于统计。"""
    text = str(error or "").lower()
    if not text:
        return "internal"
    if "timed out" in text or "timeout" in text or "超时" in text:
        return "timeout"
    if "rate limit" in text or "频率超限" in text or "429" in text or "too many requests" in text:
        return "rate_limit"
    if "502" in text or "503" in text or "504" in text or "upstream" in text or "service unavailable" in text:
        return "upstream"
    if "401" in text or "unauthorized" in text or "invalid api key" in text or "鉴权" in text or "无权限" in text:
        return "auth"
    if "json" in text and ("parse" in text or "解析" in text or "decode" in text):
        return "json_parse"
    if "budget" in text or "预算" in text:
        return "budget"
    if "connection" in text or "network" in text or "dns" in text or "ssl" in text:
        return "network"
    if "tool" in text or "工具" in text:
        return "tool_error"
    return "internal"


class ObsStore:
    """观测库。一个进程一个实例，写入线程单条，查询走独立连接。"""

    def __init__(self, path: Optional[str] = None):
        self.path = path or os.getenv("OBS_DB_PATH") or DEFAULT_DB
        self._queue: "queue.Queue[tuple]" = queue.Queue(maxsize=20000)
        self._lock = threading.Lock()
        self._seq: Dict[str, int] = {}
        self._started_at: Dict[str, float] = {}
        self._dropped = 0
        self._last_write = ""
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._initialized = False
        self._started = False

    # ---------- 初始化 ----------

    def init(self) -> None:
        if self._initialized:
            return
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        conn = sqlite3.connect(self.path)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    task_id TEXT PRIMARY KEY,
                    session_id TEXT,
                    query TEXT,
                    source TEXT,
                    status TEXT,
                    started_at TEXT,
                    finished_at TEXT,
                    duration_ms INTEGER,
                    model TEXT,
                    plan_json TEXT,
                    verdict_stance TEXT,
                    conviction REAL,
                    evidence_count INTEGER,
                    llm_calls INTEGER,
                    tool_calls INTEGER,
                    error_type TEXT,
                    error TEXT,
                    decision_id TEXT,
                    degraded INTEGER,
                    trace_json TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_runs_started ON runs(started_at);
                CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
                CREATE INDEX IF NOT EXISTS idx_runs_session ON runs(session_id);

                CREATE TABLE IF NOT EXISTS run_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    ts TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    type TEXT,
                    stage TEXT,
                    agent TEXT,
                    status TEXT,
                    duration_ms INTEGER,
                    payload_json TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_events_task ON run_events(task_id, sequence);

                CREATE TABLE IF NOT EXISTS llm_calls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT,
                    ts TEXT,
                    stage TEXT,
                    agent TEXT,
                    model TEXT,
                    duration_ms INTEGER,
                    status TEXT,
                    prompt_chars INTEGER,
                    output_chars INTEGER,
                    prompt_tokens INTEGER,
                    completion_tokens INTEGER,
                    prompt_hash TEXT,
                    error TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_llm_task ON llm_calls(task_id);
                CREATE INDEX IF NOT EXISTS idx_llm_status ON llm_calls(status);

                CREATE TABLE IF NOT EXISTS tool_calls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT,
                    ts TEXT,
                    stage TEXT,
                    agent TEXT,
                    tool TEXT,
                    params_json TEXT,
                    duration_ms INTEGER,
                    status TEXT,
                    error TEXT,
                    data_chars INTEGER,
                    result_digest TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_tool_task ON tool_calls(task_id);
                CREATE INDEX IF NOT EXISTS idx_tool_status ON tool_calls(tool, status);

                CREATE TABLE IF NOT EXISTS obs_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
                """
            )
            conn.commit()
        finally:
            conn.close()
        self._initialized = True

    def start(self) -> None:
        self.init()
        if self._started:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._writer_loop, name="obs-writer", daemon=True)
        self._thread.start()
        self._started = True

    def stop(self) -> None:
        if not self._started:
            return
        self._stop.set()
        try:
            self._queue.join()
        except Exception:
            pass
        if self._thread is not None:
            self._thread.join(timeout=2)
        self._started = False

    def flush(self) -> None:
        if self._started:
            try:
                self._queue.join()
            except Exception:
                pass

    # ---------- 写入 ----------

    def _writer_loop(self) -> None:
        conn = sqlite3.connect(self.path)
        try:
            while not self._stop.is_set():
                try:
                    item = self._queue.get(timeout=0.5)
                except queue.Empty:
                    continue
                batch = [item]
                while len(batch) < 200:
                    try:
                        batch.append(self._queue.get_nowait())
                    except queue.Empty:
                        break
                try:
                    with conn:
                        for sql, params in batch:
                            conn.execute(sql, params)
                    self._last_write = now_iso()
                except Exception:
                    pass
                finally:
                    for _ in batch:
                        self._queue.task_done()
        finally:
            conn.close()

    def submit(self, sql: str, params: tuple) -> None:
        self.init()
        if not self._started:
            try:
                conn = sqlite3.connect(self.path)
                try:
                    with conn:
                        conn.execute(sql, params)
                    self._last_write = now_iso()
                finally:
                    conn.close()
            except Exception:
                self._dropped += 1
            return
        try:
            self._queue.put_nowait((sql, params))
        except queue.Full:
            self._dropped += 1

    # ---------- 运行 ----------

    def run_start(
        self,
        task_id: str,
        session_id: str = "",
        query: str = "",
        source: str = "agent",
        model: str = "",
    ) -> None:
        ts = now_iso()
        self._started_at[task_id] = time.time()
        self.submit(
            "INSERT OR REPLACE INTO runs "
            "(task_id, session_id, query, source, status, started_at, model) "
            "VALUES (?, ?, ?, ?, 'running', ?, ?)",
            (task_id, session_id, truncate(query, 2048), source, ts, model),
        )

    def run_update(self, task_id: str, **fields: Any) -> None:
        clean = {key: value for key, value in fields.items() if key in RUN_FIELDS}
        if not clean:
            return
        sets = ", ".join(f"{key} = ?" for key in clean)
        self.submit(f"UPDATE runs SET {sets} WHERE task_id = ?", (*clean.values(), task_id))

    def run_finish(
        self,
        task_id: str,
        status: str,
        error_type: str = "",
        error: str = "",
        **fields: Any,
    ) -> None:
        fields["status"] = status
        if not error_type and error:
            error_type = classify_error(error)
        fields["error_type"] = error_type
        fields["error"] = truncate(error, 2000)
        fields["finished_at"] = now_iso()
        started = self._started_at.pop(task_id, None)
        if started is not None:
            fields["duration_ms"] = int((time.time() - started) * 1000)
        clean = {key: value for key, value in fields.items() if key in RUN_FIELDS}
        sets = ", ".join(f"{key} = ?" for key in clean)
        self.submit(f"UPDATE runs SET {sets} WHERE task_id = ?", (*clean.values(), task_id))

    # ---------- 事件 / LLM / 工具 ----------

    def _next_sequence(self, task_id: str) -> int:
        with self._lock:
            value = self._seq.get(task_id, 0) + 1
            self._seq[task_id] = value
            return value

    def record_event(
        self,
        task_id: str,
        event_type: str,
        data: Any = None,
        stage: str = "",
        agent: str = "",
        status: str = "",
        duration_ms: Optional[int] = None,
    ) -> None:
        if not task_id:
            return
        payload = truncate(json.dumps(redact(data or {}), ensure_ascii=False, default=str))
        self.submit(
            "INSERT INTO run_events "
            "(task_id, ts, sequence, type, stage, agent, status, duration_ms, payload_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                task_id, now_iso(), self._next_sequence(task_id), event_type,
                stage, agent, status, duration_ms, payload,
            ),
        )

    def record_llm(
        self,
        task_id: str,
        stage: str,
        agent: str,
        model: str,
        duration_ms: int,
        status: str,
        prompt_chars: int = 0,
        output_chars: int = 0,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        prompt_hash: str = "",
        error: str = "",
    ) -> None:
        if not task_id:
            return
        self.submit(
            "INSERT INTO llm_calls "
            "(task_id, ts, stage, agent, model, duration_ms, status, prompt_chars, "
            "output_chars, prompt_tokens, completion_tokens, prompt_hash, error) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                task_id, now_iso(), stage, agent, model, duration_ms, status,
                prompt_chars, output_chars, prompt_tokens, completion_tokens,
                prompt_hash, truncate(error, 500),
            ),
        )

    def record_tool(
        self,
        task_id: str,
        stage: str,
        agent: str,
        tool: str,
        params: Any,
        duration_ms: int,
        status: str,
        error: str = "",
        data_chars: int = 0,
        result_digest: str = "",
    ) -> None:
        if not task_id:
            return
        self.submit(
            "INSERT INTO tool_calls "
            "(task_id, ts, stage, agent, tool, params_json, duration_ms, status, "
            "error, data_chars, result_digest) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                task_id, now_iso(), stage, agent, tool,
                truncate(json.dumps(redact(params or {}), ensure_ascii=False, default=str), 1024),
                duration_ms, status, truncate(error, 500), data_chars, result_digest,
            ),
        )

    # ---------- 查询 ----------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=5)
        conn.row_factory = sqlite3.Row
        return conn

    def _rows(self, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        self.flush()
        conn = self._connect()
        try:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def list_runs(
        self,
        status: Optional[str] = None,
        limit: int = 20,
        session_id: Optional[str] = None,
        since: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        clauses, params = [], []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if session_id:
            clauses.append("session_id = ?")
            params.append(session_id)
        if since:
            clauses.append("started_at >= ?")
            params.append(since)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(max(1, min(int(limit or 20), 200)))
        return self._rows(
            f"SELECT * FROM runs {where} ORDER BY started_at DESC LIMIT ?", tuple(params)
        )

    def get_run(self, task_id: str) -> Optional[Dict[str, Any]]:
        rows = self._rows("SELECT * FROM runs WHERE task_id = ?", (task_id,))
        return rows[0] if rows else None

    def list_events(self, task_id: str, after_sequence: int = 0, limit: int = 1000) -> List[Dict[str, Any]]:
        return self._rows(
            "SELECT * FROM run_events WHERE task_id = ? AND sequence > ? "
            "ORDER BY sequence ASC LIMIT ?",
            (task_id, int(after_sequence or 0), max(1, min(int(limit or 1000), 5000))),
        )

    def list_llm(self, task_id: str, limit: int = 500) -> List[Dict[str, Any]]:
        return self._rows(
            "SELECT * FROM llm_calls WHERE task_id = ? ORDER BY id ASC LIMIT ?",
            (task_id, max(1, min(int(limit or 500), 2000))),
        )

    def list_tools(self, task_id: str, limit: int = 500) -> List[Dict[str, Any]]:
        return self._rows(
            "SELECT * FROM tool_calls WHERE task_id = ? ORDER BY id ASC LIMIT ?",
            (task_id, max(1, min(int(limit or 500), 2000))),
        )

    def stats(self, window_hours: int = 24) -> Dict[str, Any]:
        since = (datetime.now() - timedelta(hours=max(1, int(window_hours or 24)))).isoformat(timespec="milliseconds")
        runs = self._rows("SELECT * FROM runs WHERE started_at >= ?", (since,))
        llm = self._rows("SELECT status, duration_ms FROM llm_calls WHERE ts >= ?", (since,))
        tools = self._rows("SELECT tool, status FROM tool_calls WHERE ts >= ?", (since,))

        durations = sorted(
            r["duration_ms"] for r in runs
            if r.get("status") == "completed"
            and r.get("duration_ms") is not None
            and r.get("duration_ms") > 0
        )

        def pct(values: List[int], p: float) -> Optional[float]:
            if not values:
                return None
            index = min(len(values) - 1, max(0, int(round((len(values) - 1) * p))))
            return values[index]

        error_types: Dict[str, int] = {}
        for run in runs:
            if run.get("error_type"):
                error_types[run["error_type"]] = error_types.get(run["error_type"], 0) + 1

        tool_failures: Dict[str, int] = {}
        for item in tools:
            if item.get("status") in ("failed", "partial"):
                tool_failures[item["tool"]] = tool_failures.get(item["tool"], 0) + 1

        llm_failures = sum(1 for item in llm if item.get("status") != "ok")
        phase_totals: Dict[str, List[int]] = {}
        for run in runs:
            try:
                trace = json.loads(run.get("trace_json") or "{}")
            except Exception:
                continue
            for phase in trace.get("phases") or []:
                name = phase.get("phase") or ""
                duration = phase.get("duration_ms")
                if name and isinstance(duration, (int, float)):
                    phase_totals.setdefault(name, []).append(int(duration))

        completed = sum(1 for r in runs if r.get("status") == "completed")
        failed = sum(1 for r in runs if r.get("status") == "failed")

        return {
            "window_hours": window_hours,
            "tasks": {
                "total": len(runs),
                "completed": completed,
                "failed": failed,
                "failure_rate": round(failed / len(runs), 4) if runs else 0.0,
                "duration_p50_ms": pct(durations, 0.5),
                "duration_p95_ms": pct(durations, 0.95),
            },
            "llm": {
                "calls": len(llm),
                "failures": llm_failures,
                "failure_rate": round(llm_failures / len(llm), 4) if llm else 0.0,
                "avg_duration_ms": int(sum(i.get("duration_ms") or 0 for i in llm) / len(llm)) if llm else None,
            },
            "tools": {
                "calls": len(tools),
                "failures": sum(tool_failures.values()),
                "top_failures": sorted(tool_failures.items(), key=lambda x: -x[1])[:10],
            },
            "error_types": error_types,
            "phase_avg_ms": {
                name: int(sum(values) / len(values)) for name, values in sorted(phase_totals.items())
            },
        }

    def health(self) -> Dict[str, Any]:
        size = None
        try:
            size = os.path.getsize(self.path)
        except OSError:
            pass
        try:
            free_mb = int(shutil.disk_usage(os.path.dirname(self.path)).free / (1024 * 1024))
        except OSError:
            free_mb = None
        return {
            "db_path": self.path,
            "db_size_bytes": size,
            "db_ok": self._initialized,
            "writer_started": self._started,
            "queue_size": self._queue.qsize(),
            "dropped": self._dropped,
            "last_write": self._last_write,
            "disk_free_mb": free_mb,
        }

    def cleanup(self, run_days: int = 90, event_days: int = 30) -> int:
        removed = 0
        run_cutoff = (datetime.now() - timedelta(days=max(1, run_days))).isoformat(timespec="milliseconds")
        event_cutoff = (datetime.now() - timedelta(days=max(1, event_days))).isoformat(timespec="milliseconds")
        for sql, params in (
            ("DELETE FROM runs WHERE started_at < ?", (run_cutoff,)),
            ("DELETE FROM run_events WHERE ts < ?", (event_cutoff,)),
            ("DELETE FROM llm_calls WHERE ts < ?", (event_cutoff,)),
            ("DELETE FROM tool_calls WHERE ts < ?", (event_cutoff,)),
        ):
            try:
                conn = sqlite3.connect(self.path)
                try:
                    with conn:
                        cursor = conn.execute(sql, params)
                        removed += cursor.rowcount or 0
                finally:
                    conn.close()
            except Exception:
                pass
        return removed


_store: Optional[ObsStore] = None
_store_lock = threading.Lock()


def get_store() -> ObsStore:
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = ObsStore()
    return _store


def reset_store_for_tests() -> None:
    global _store
    with _store_lock:
        if _store is not None:
            _store.stop()
        _store = None
