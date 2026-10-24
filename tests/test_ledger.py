#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""EvidenceLedger 单元测试（纯逻辑，无 LLM / 网络）"""

from __future__ import annotations

from agents.ledger import EvidenceLedger
from agents.state import LedgerEvidence, ToolResult


def _ledger(as_of=None):
    return EvidenceLedger(as_of=as_of)


def test_add_dedup_merges_same_statement():
    ledger = _ledger()
    first = ledger.add(LedgerEvidence(
        evidence_id="", asset_id="600519", category="fundamental",
        statement="2026Q2 营收同比 -15.2%",
    ))
    second = ledger.add(LedgerEvidence(
        evidence_id="", asset_id="600519", category="fundamental",
        statement="2026Q2 营收同比 -15.2%",
    ))
    assert first.evidence_id == second.evidence_id
    assert first.seen_count == 2
    assert ledger.count() == 1


def test_evidence_ids_are_monotonic():
    ledger = _ledger()
    ids = [
        ledger.add(LedgerEvidence(evidence_id="", statement=f"事实 {i}")).evidence_id
        for i in range(3)
    ]
    assert ids == ["EV-0001", "EV-0002", "EV-0003"]


def test_pit_marks_future_evidence_as_conflict():
    ledger = _ledger(as_of="2026-06-30")
    item = ledger.add(LedgerEvidence(
        evidence_id="",
        statement="2026Q3 营收同比 +20%",
        source_time="2026-10-20",
        confidence=0.9,
    ))
    assert item.conflict is True
    assert item.confidence <= 0.1


def test_pit_keeps_past_evidence_clean():
    ledger = _ledger(as_of="2026-06-30")
    item = ledger.add(LedgerEvidence(
        evidence_id="",
        statement="2026Q1 营收同比 +5%",
        source_time="2026-04-28",
    ))
    assert item.conflict is False


def test_validate_returns_missing_ids():
    ledger = _ledger()
    ledger.add(LedgerEvidence(evidence_id="", statement="事实 A"))
    missing = ledger.validate(["EV-0001", "EV-9999"])
    assert missing == ["EV-9999"]


def test_record_tool_creates_evidence_from_summary():
    ledger = _ledger()
    result = ToolResult(
        tool_name="cn_stock_history",
        status="success",
        data={"summary": {"latest_close": 12.5, "total_return_pct": 3.2}, "symbol": "600519"},
    )
    items = ledger.record_tool("MarketAnalyst", "cn_stock_history", {"symbol": "600519"}, result)
    assert len(items) == 1
    assert items[0].category == "market"
    assert items[0].asset_id == "600519"
    assert items[0].source_tool == "cn_stock_history"


def test_record_tool_skips_failed_result():
    ledger = _ledger()
    result = ToolResult(tool_name="cn_stock_history", status="failed", error="boom")
    assert ledger.record_tool("MarketAnalyst", "cn_stock_history", {}, result) == []


def test_format_for_prompt_contains_ids_and_caliber():
    ledger = _ledger()
    ledger.add(LedgerEvidence(
        evidence_id="", category="valuation", statement="PE(TTM) 22.5 倍",
        caliber="PE(TTM)", source_time="2026-06-30",
    ))
    text = ledger.format_for_prompt()
    assert "EV-0001" in text
    assert "PE(TTM)" in text


def test_summary_counts_by_category():
    ledger = _ledger()
    ledger.add(LedgerEvidence(evidence_id="", category="market", statement="A"))
    ledger.add(LedgerEvidence(evidence_id="", category="market", statement="B"))
    ledger.add(LedgerEvidence(evidence_id="", category="news", statement="C"))
    assert ledger.summary() == {"market": 2, "news": 1}
