#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Pipeline 离线端到端冒烟测试

用 FakeLLM + FakeAnalyst 跑通 L0-L6，验证：
- 分析师产出被解析进 Ledger
- 多空论点、辩论、裁决、质检串起来
- 最终 answer 的结构与证据引用
全程不联网、不写真实数据库。
"""

from __future__ import annotations

import json

import pytest

from agents.pipeline import Pipeline
from agents.state import LedgerEvidence, AgentResult, Asset, AssetType


def _thesis(side: str, claim_id: str, evidence_id: str, statement: str) -> dict:
    return {
        "core_claim": f"{side} 核心论点",
        "confidence": 0.7,
        "claims": [
            {
                "claim_id": f"CLM-{side.upper()}-{index:02d}",
                "statement": f"{statement}（第 {index} 条）",
                "evidence_ids": [evidence_id if index < 3 else "EV-0003"],
                "reasoning": "证据直接支持",
                "strength": "high",
                "assumptions": ["行业需求稳定"],
                "falsifiers": ["下季度营收同比低于 5%"],
                "time_horizon": "1-3 个月",
            }
            for index in range(1, 4)
        ],
        "key_assumptions": ["行业需求稳定"],
        "kill_criteria": ["营收连续两季负增长"],
        "unanswered_gaps": [],
    }


class FakeLLM:
    """按 system 提示词路由到预设响应"""

    def __init__(self, *args, **kwargs):
        pass

    def json(self, system, user, max_tokens=4096, required_keys=None, temperature=None):
        if "投研主管" in system:
            return {
                "intent": "single_asset_research",
                "horizon": "medium",
                "optional_analysts": ["news"],
                "debate": True,
                "focus_questions": ["营收增速是否可持续"],
                "reason": "测试计划",
            }
        if "请攻击对方最强的论点" in system:
            target = "CLM-BEAR-01" if "多方" in system else "CLM-BULL-01"
            return {"attacks": [{
                "target_claim_id": target,
                "attack_type": "priced_in",
                "argument": "该论点没有考虑估值分位",
                "cited_evidence_ids": ["EV-0003"],
            }]}
        if "请逐条回应针对你的攻击" in system:
            target = "CLM-BULL-01" if "多方" in system else "CLM-BEAR-01"
            return {
                "responses": [{
                    "target_claim_id": target,
                    "action": "revise",
                    "argument": "下调强度并补充估值证据",
                    "concession": "",
                }],
                "no_concession_reason": "",
            }
        if "多方研究员" in system:
            return _thesis("bull", "CLM-BULL-01", "EV-0002", "营收同比 12.5% 支撑估值")
        if "空方研究员" in system:
            return _thesis("bear", "CLM-BEAR-01", "EV-0001", "近 20 日涨幅 8.2% 已反映预期")
        if "你现在只做独立判断" in system:
            return {
                "stance": "bullish",
                "conviction": 0.65,
                "key_drivers": [{"text": "营收增速 12.5%", "evidence_id": "EV-0002"}],
                "uncertainties": ["估值分位偏高"],
            }
        if "现在需要给出最终裁决" in system:
            return {
                "stance": "bullish",
                "conviction": 0.7,
                "summary": "营收增速 12.5% 支撑当前估值，但涨幅已部分反映预期",
                "key_drivers": ["营收增速 12.5%（EV-0002）"],
                "disagreement_map": [{
                    "topic": "涨幅是否已反映预期",
                    "bull_view": "尚未反映",
                    "bear_view": "已经反映",
                    "resolvable": "needs_data",
                    "resolution": "需要估值分位数据",
                }],
                "falsifiers_to_watch": ["单季营收同比转负"],
                "what_would_change_my_mind": ["毛利率显著下滑"],
                "position_hint": "0%-20% 试探仓位",
                "time_frame": "1-3 个月",
                "structured_risks": [{
                    "type": "市场", "desc": "估值分位偏高带来的回撤风险",
                    "probability": "medium", "impact": "medium", "priced_in": False,
                }],
                "revision_reason": "空白辩论未改变判断，估值风险已写入风险项",
                "confidence_calibration": "最可能错在对增速持续性的假设",
                "evidence_ids": ["EV-0001", "EV-0002", "EV-0003"],
            }
        if "投研质检员" in system:
            return {"issues": []}
        return {}


class FakeAnalyst:
    """返回契约格式的分析师产出，覆盖不同类别"""

    def __init__(self, name: str, payload: dict, ledger=None):
        self.name = name
        self.payload = payload
        self.ledger = ledger
        self.max_iterations = 2

    def run(self, task):
        refs = []
        if self.ledger is not None:
            for item in self.payload["evidence"]:
                stored = self.ledger.add(LedgerEvidence(evidence_id="", **item))
                refs.append(stored.evidence_id)
        return AgentResult(
            agent_name=self.name,
            conclusion=json.dumps({
                "decision": "final",
                "highlights": self.payload["evidence"],
                "gaps": [],
                "coverage": {"asked": 1, "answered": 1, "failed": 0},
            }, ensure_ascii=False),
            evidence_refs=refs,
        )


def test_pipeline_end_to_end(monkeypatch):
    import agents.pipeline as pipeline_module

    asset = Asset(asset_type=AssetType.CN_STOCK, symbol="600519", name="贵州茅台")

    monkeypatch.setattr(Pipeline, "_settle_in_background", lambda self: None)
    monkeypatch.setattr(Pipeline, "_resolve_assets", lambda self, q, s: [asset])
    monkeypatch.setattr(pipeline_module, "LLM", FakeLLM)

    payloads = {
        "market": {"evidence": [{
            "category": "market", "statement": "近 20 日涨幅 8.2%", "value": 8.2,
            "unit": "%", "caliber": "前复权", "source_tool": "cn_stock_history",
            "source_time": "2026-06-30", "confidence": 0.9,
        }]},
        "fundamental": {"evidence": [{
            "category": "fundamental", "statement": "2026Q1 营收同比 12.5%", "value": 12.5,
            "unit": "%", "caliber": "单季同比", "source_tool": "stock_financial_summary",
            "source_time": "2026-04-28", "confidence": 0.9,
        }]},
        "news": {"evidence": [{
            "category": "news", "statement": "PE(TTM) 22.5 倍，处于近三年中位", "value": 22.5,
            "unit": "倍", "caliber": "PE(TTM)", "source_tool": "asset_news_search",
            "source_time": "2026-06-29", "confidence": 0.7,
        }]},
    }

    def fake_build(key, **kwargs):
        label = {"market": "MarketAnalyst", "fundamental": "FundamentalAnalyst", "news": "NewsAnalyst"}[key]
        return FakeAnalyst(label, payloads[key], ledger=kwargs.get("ledger"))

    monkeypatch.setattr(pipeline_module.analyst_registry, "build_analyst", fake_build)

    saved = {}
    monkeypatch.setattr(
        pipeline_module.decision_store, "save_decision",
        lambda record: saved.setdefault("record", record) is not None or record["decision_id"],
    )
    monkeypatch.setattr(pipeline_module.decision_store, "save_trace", lambda *a, **k: None)

    result = Pipeline(task_id="task_test").run(
        session_id="s1",
        query="分析贵州茅台",
        as_of="2026-06-30",
    )

    assert result["verdict"]["stance"] == "bullish"
    assert result["verdict"]["blind_stance"] == "bullish"
    assert result["plan"]["debate"] is True
    assert len(result["evidence"]) == 3
    assert len(result["debate"]["turns"]) >= 2
    actions = {turn["action"] for turn in result["debate"]["turns"]}
    assert "attack" in actions
    assert "revise" in actions
    assert result["answer"]["summary"]
    assert result["verification"]["passed"] is True
    assert result["decision_id"].startswith("dec_")
    assert result["decision_id"] in saved or saved.get("record", {}).get("decision_id")
    # 证据引用必须可追溯
    for ref in result["answer"]["evidence_refs"]:
        assert ref in {item["evidence_id"] for item in result["evidence"]}


def test_pipeline_degrades_when_analyst_fails(monkeypatch):
    import agents.pipeline as pipeline_module

    asset = Asset(asset_type=AssetType.CN_STOCK, symbol="600519", name="贵州茅台")

    monkeypatch.setattr(Pipeline, "_settle_in_background", lambda self: None)
    monkeypatch.setattr(Pipeline, "_resolve_assets", lambda self, q, s: [asset])
    monkeypatch.setattr(pipeline_module, "LLM", FakeLLM)
    monkeypatch.setattr(
        pipeline_module.analyst_registry, "build_analyst",
        lambda key, **kwargs: (_ for _ in ()).throw(RuntimeError("analyst down")),
    )
    monkeypatch.setattr(pipeline_module.decision_store, "save_decision", lambda r: "dec_x")
    monkeypatch.setattr(pipeline_module.decision_store, "save_trace", lambda *a, **k: None)

    result = Pipeline(task_id="task_degraded").run(
        session_id="s1", query="分析贵州茅台", as_of="2026-06-30",
    )

    # 分析师全部失败 → 不应崩溃，且置信度被封顶
    assert result["answer"]["confidence"] <= 0.5
    assert result["verification"]["passed"] is False
