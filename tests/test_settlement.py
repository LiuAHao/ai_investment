#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""结算计算测试（注入价格，不联网）"""

from __future__ import annotations

from datetime import datetime

import pytest

from memory import settlement
from memory.settlement import (
    build_reflection,
    compute_alpha,
    compute_return,
    horizon_days,
    settle_pending,
)


def test_compute_return():
    assert compute_return(100, 110) == pytest.approx(0.1)
    assert compute_return(100, 90) == pytest.approx(-0.1)
    assert compute_return(0, 100) == 0.0


def test_compute_alpha():
    assert compute_alpha(0.10, 0.04) == pytest.approx(0.06)


def test_horizon_days_mapping():
    assert horizon_days("short") == 5
    assert horizon_days("medium") == 20
    assert horizon_days("long") == 60
    assert horizon_days("unknown") == 20


def test_reflection_hit_and_miss():
    record = {
        "as_of": "2026-01-05",
        "query": "测试标的",
        "stance": "bullish",
        "payload": {"verdict": {"conviction": 0.8, "falsifiers_to_watch": ["跌破 60 日线"]}},
    }
    hit = build_reflection(record, {"hit": True, "alpha": 0.02, "return": 0.05, "horizon_days": 20})
    assert hit["hit"] is True
    assert "判断方向与后续走势一致" in hit["text"]

    miss = build_reflection(record, {"hit": False, "alpha": -0.05, "return": -0.08, "horizon_days": 20})
    assert miss["miss_reason"] == "logic_or_overconfidence"


def test_settle_pending_uses_injected_prices(monkeypatch):
    records = [{
        "decision_id": "dec_test",
        "as_of": "2026-01-05",
        "horizon": "medium",
        "stance": "bullish",
        "payload": {
            "asset_ids": ["600519"],
            "price_snapshot": {"symbol": "600519", "price": 100.0},
            "benchmark": "000300",
            "verdict": {"conviction": 0.7, "falsifiers_to_watch": []},
        },
    }]
    updates = []

    monkeypatch.setattr(settlement.decision_store, "list_unsettled", lambda limit=50: records)
    monkeypatch.setattr(
        settlement.decision_store,
        "update_settlement",
        lambda decision_id, payload, reflection=None: updates.append((decision_id, payload, reflection)),
    )

    def fake_fetcher(symbol, start, days):
        return {"entry": 100.0, "exit": 110.0, "bars": 30}

    result = settle_pending(
        price_fetcher=fake_fetcher,
        now=datetime(2026, 3, 1),
    )
    assert len(result) == 1
    assert result[0]["hit"] is True
    assert result[0]["return"] == 0.1
    # 基准同涨幅 → alpha 为 0
    assert result[0]["alpha"] == 0.0
    assert updates and updates[0][0] == "dec_test"


def test_settle_pending_skips_not_due(monkeypatch):
    records = [{
        "decision_id": "dec_due",
        "as_of": "2026-03-01",
        "horizon": "long",
        "stance": "neutral",
        "payload": {"asset_ids": ["600519"], "price_snapshot": {"symbol": "600519"}},
    }]
    monkeypatch.setattr(settlement.decision_store, "list_unsettled", lambda limit=50: records)
    monkeypatch.setattr(settlement.decision_store, "update_settlement", lambda *a, **k: None)
    result = settle_pending(price_fetcher=lambda *a: {"entry": 1, "exit": 2}, now=datetime(2026, 3, 10))
    assert result == []
