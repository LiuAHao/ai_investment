#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""历史会话持久化测试：确保 v4 状态（证据/辩论/裁决/阶段）写入 turn"""

from __future__ import annotations

import api.routes.agent as agent_route
import agents.memory as memory_module


def _result():
    return {
        "query": "分析贵州茅台",
        "plan": {"agents": ["MarketAnalyst", "FundamentalAnalyst"]},
        "agent_results": [{
            "agent_name": "MarketAnalyst",
            "conclusion": "结论",
            "thinking_log": ["思考"],
            "evidence_refs": ["EV-0001"],
            "tool_calls": [{
                "tool_name": "cn_stock_history",
                "status": "success",
                "latency_ms": 120,
                "data": {"summary": {"latest_close": 1300}},
            }],
            "error": None,
            "degraded": False,
        }],
        "orchestrator": {"thoughts": ["计划"], "plan": ["MarketAnalyst"], "reason": "r"},
        "answer": {
            "summary": "总体判断",
            "key_points": ["要点"],
            "confidence": 0.6,
        },
        "evidence": [{"evidence_id": "EV-0001", "category": "market", "statement": "近 20 日涨幅 8%"}],
        "thesis": {"bull": {"claims": [{"claim_id": "C1"}]}, "bear": {"claims": []}},
        "debate": {"enabled": True, "turns": [{"round": 1, "side": "bull", "action": "attack"}]},
        "verdict": {"stance": "bullish", "conviction": 0.6, "blind_stance": "neutral"},
        "verification": {"passed": True, "issues": []},
        "trace": {"total_ms": 1000, "phases": [{"phase": "L1", "duration_ms": 900, "degraded": False}]},
        "decision_id": "dec_test",
    }


def test_save_session_turn_persists_v4_state(monkeypatch):
    captured = {}

    class FakeMemory:
        def add_turn(self, session_id, query, answer, agent_results,
                     plan=None, orchestrator=None, extras=None):
            captured.update({
                "session_id": session_id,
                "query": query,
                "answer": answer,
                "agent_results": agent_results,
                "plan": plan,
                "orchestrator": orchestrator,
                "extras": extras,
            })

    monkeypatch.setattr(memory_module, "get_session_memory", lambda: FakeMemory())

    agent_route._save_session_turn("s1", "分析贵州茅台", _result())

    extras = captured["extras"]
    assert extras["evidence"][0]["evidence_id"] == "EV-0001"
    assert extras["debate"]["turns"][0]["action"] == "attack"
    assert extras["verdict"]["stance"] == "bullish"
    assert extras["thesis"]["bull"]["claims"][0]["claim_id"] == "C1"
    assert extras["verification"]["passed"] is True
    assert extras["trace"]["phases"][0]["phase"] == "L1"
    assert extras["decision_id"] == "dec_test"
    assert captured["plan"] == ["MarketAnalyst", "FundamentalAnalyst"]
    assert captured["answer"].summary == "总体判断"


def test_save_session_turn_tolerates_missing_v4_fields(monkeypatch):
    captured = {}

    class FakeMemory:
        def add_turn(self, session_id, query, answer, agent_results,
                     plan=None, orchestrator=None, extras=None):
            captured["extras"] = extras

    monkeypatch.setattr(memory_module, "get_session_memory", lambda: FakeMemory())

    agent_route._save_session_turn("s1", "旧格式", {
        "answer": {"summary": "旧结论"},
        "agent_results": [],
    })

    assert captured["extras"]["evidence"] == []
    assert captured["extras"]["verdict"] == {}
    assert captured["extras"]["trace"] == {}
