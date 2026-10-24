#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""可观测性存储与脱敏测试（不依赖网络）。"""

from __future__ import annotations

import json

from obs.store import ObsStore, classify_error, redact, truncate


def _store(tmp_path) -> ObsStore:
    store = ObsStore(str(tmp_path / "obs.sqlite"))
    store.start()
    return store


def test_run_lifecycle(tmp_path):
    store = _store(tmp_path)
    try:
        store.run_start("task_1", "sess_1", "分析贵州茅台", model="m")
        store.run_update("task_1", evidence_count=12, verdict_stance="bearish")
        store.run_finish("task_1", "completed", decision_id="dec_1", degraded=0)
        store.flush()

        run = store.get_run("task_1")
        assert run["status"] == "completed"
        assert run["session_id"] == "sess_1"
        assert run["evidence_count"] == 12
        assert run["verdict_stance"] == "bearish"
        assert run["decision_id"] == "dec_1"
        assert run["duration_ms"] is not None
    finally:
        store.stop()


def test_events_sequence_and_incremental(tmp_path):
    store = _store(tmp_path)
    try:
        for index in range(3):
            store.record_event("task_1", "phase_started", {"i": index}, stage="L1")
        store.flush()
        events = store.list_events("task_1")
        assert [e["sequence"] for e in events] == [1, 2, 3]
        later = store.list_events("task_1", after_sequence=2)
        assert len(later) == 1 and later[0]["sequence"] == 3
    finally:
        store.stop()


def test_llm_and_tool_records(tmp_path):
    store = _store(tmp_path)
    try:
        store.record_llm("task_1", "L2", "Bull", "model-x", 1200, "ok", 100, 50, 10, 20, "hash")
        store.record_llm("task_1", "L2", "Bear", "model-x", 3000, "timeout", 100, 0, None, None, "hash2", "timed out")
        store.record_tool("task_1", "L1", "Market", "cn_stock_history", {"symbol": "600519"}, 800, "success", "", 500, "digest")
        store.record_tool("task_1", "L1", "News", "asset_news_search", {"keywords": ["茅台"]}, 2000, "failed", "网络错误", 0, "")
        store.flush()

        llm = store.list_llm("task_1")
        tools = store.list_tools("task_1")
        assert len(llm) == 2 and sum(1 for item in llm if item["status"] != "ok") == 1
        assert len(tools) == 2 and sum(1 for item in tools if item["status"] == "failed") == 1
    finally:
        store.stop()


def test_stats_and_health(tmp_path):
    store = _store(tmp_path)
    try:
        store.run_start("task_1", "s", "q")
        store.run_finish(
            "task_1", "completed",
            trace_json=json.dumps({"phases": [{"phase": "L1", "duration_ms": 1000}]}),
        )
        store.run_start("task_2", "s", "q")
        store.run_finish("task_2", "failed", error=TimeoutError("timed out"))
        store.record_tool("task_1", "L1", "A", "cn_stock_history", {}, 100, "success", "", 10, "")
        store.record_tool("task_1", "L1", "B", "asset_news_search", {}, 100, "failed", "x", 0, "")
        store.flush()

        stats = store.stats(window_hours=24)
        assert stats["tasks"]["total"] == 2
        assert stats["tasks"]["completed"] == 1
        assert stats["tasks"]["failed"] == 1
        assert stats["error_types"].get("timeout") == 1
        assert stats["tools"]["top_failures"][0][0] == "asset_news_search"
        assert stats["phase_avg_ms"].get("L1") == 1000

        health = store.health()
        assert health["db_ok"] is True
        assert health["writer_started"] is True
        assert health["dropped"] == 0
    finally:
        store.stop()


def test_redact_and_classify():
    payload = {
        "symbol": "600519",
        "api_key": "sk-secret",
        "nested": {"Authorization": "Bearer xxx", "token": "abc"},
        "items": [{"password": "p", "value": 1}],
    }
    cleaned = redact(payload)
    assert cleaned["api_key"] == "***"
    assert cleaned["nested"]["Authorization"] == "***"
    assert cleaned["nested"]["token"] == "***"
    assert cleaned["items"][0]["password"] == "***"
    assert cleaned["symbol"] == "600519"

    assert classify_error("Request timed out") == "timeout"
    assert classify_error("401 Unauthorized") == "auth"
    assert classify_error("频率超限") == "rate_limit"
    assert classify_error("JSON 解析失败") == "json_parse"
    assert classify_error("unknown boom") == "internal"


def test_truncate():
    assert truncate("a" * 5000, 100) == "a" * 100
    assert truncate({"a": 1}) == '{"a": 1}'
    assert truncate(None) == ""


def test_cleanup_does_not_fail(tmp_path):
    store = _store(tmp_path)
    try:
        store.run_start("task_1", "s", "q")
        store.flush()
        removed = store.cleanup(run_days=1, event_days=1)
        assert removed >= 0
    finally:
        store.stop()
