#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""API 契约测试：任务结果必须包含 v4 前端所需字段"""

from __future__ import annotations

import time

import agents.memory as memory_module
import agents.orchestrator as orchestrator_module
from api.main import create_app


def _fake_result():
    return {
        "query": "分析贵州茅台",
        "assets": [],
        "plan": {"agents": ["MarketAnalyst"], "reason": "规则计划", "intent": "single_asset_research"},
        "agent_results": [],
        "analyst_outputs": [],
        "answer": {"summary": "总体判断", "key_points": [], "confidence": 0.6},
        "verdict": {"stance": "neutral", "conviction": 0.6, "blind_stance": "neutral"},
        "thesis": {"bull": {}, "bear": {}},
        "debate": {"enabled": True, "turns": []},
        "evidence": [{"evidence_id": "EV-0001", "category": "market", "statement": "事实"}],
        "verification": {"passed": True, "issues": []},
        "decision_id": "dec_api_test",
        "trace": {"phases": [{"phase": "L1", "duration_ms": 100}]},
        "orchestrator": {"thoughts": [], "plan": ["MarketAnalyst"], "reason": ""},
    }


class _FakeOrchestrator:
    def __init__(self, task_id: str = ""):
        self.task_id = task_id

    def run_query(self, **kwargs):
        return _fake_result()


class _FakeMemory:
    def add_turn(self, *args, **kwargs):
        return None


def test_task_result_contains_v4_fields(monkeypatch):
    monkeypatch.setattr(orchestrator_module, "OrchestratorAgent", _FakeOrchestrator)
    monkeypatch.setattr(memory_module, "get_session_memory", lambda: _FakeMemory())

    app = create_app()
    client = app.test_client()

    response = client.post("/api/agent/query", json={"query": "分析贵州茅台"})
    assert response.status_code == 202
    task_id = response.get_json()["task_id"]

    status = None
    for _ in range(60):
        status = client.get(f"/api/agent/tasks/{task_id}").get_json()
        if status.get("status") in ("completed", "failed"):
            break
        time.sleep(0.05)

    assert status["status"] == "completed", status
    result = status["result"]
    for key in (
        "evidence", "verdict", "thesis", "debate",
        "verification", "trace", "decision_id", "answer",
    ):
        assert key in result, f"missing {key}"
    assert result["verdict"]["stance"] == "neutral"
    assert result["evidence"][0]["evidence_id"] == "EV-0001"
