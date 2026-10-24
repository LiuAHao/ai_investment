#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Verifier 机械校验测试（不调用 LLM）"""

from __future__ import annotations

from agents.ledger import EvidenceLedger
from agents.state import Claim, LedgerEvidence, ResearchPlan, Thesis, Verdict
from agents.verifier import Verifier


def _ledger():
    ledger = EvidenceLedger(as_of="2026-06-30")
    ledger.add(LedgerEvidence(
        evidence_id="", asset_id="600519", category="market",
        statement="近 20 日涨幅 8.2%", value=8.2, unit="%", source_time="2026-06-30",
    ))
    ledger.add(LedgerEvidence(
        evidence_id="", asset_id="600519", category="fundamental",
        statement="2026Q1 营收同比 12.5%", value=12.5, unit="%", source_time="2026-04-28",
    ))
    ledger.add(LedgerEvidence(
        evidence_id="", asset_id="600519", category="valuation",
        statement="PE(TTM) 22.5 倍", value=22.5, caliber="PE(TTM)", source_time="2026-06-30",
    ))
    return ledger


def _claim(side="bull", evidence_ids=None, statement="营收增速 12.5% 支撑估值", strength="medium"):
    return Claim(
        claim_id=f"CLM-{side.upper()}-01",
        side=side,
        statement=statement,
        evidence_ids=["EV-0002"] if evidence_ids is None else evidence_ids,
        strength=strength,
        falsifiers=["下季度营收增速低于 5%"],
    )


def _verdict(**kwargs):
    payload = {
        "stance": "bullish",
        "conviction": 0.7,
        "summary": "基本面稳健，估值合理",
        "key_drivers": ["营收增速 12.5%"],
        "structured_risks": [{"type": "市场", "desc": "波动风险", "probability": "medium", "impact": "medium"}],
    }
    payload.update(kwargs)
    return Verdict(**payload)


def _plan():
    return ResearchPlan(focus_questions=["营收增速是否可持续"])


def test_valid_case_passes():
    report = Verifier(_ledger()).check_mechanical(
        bull=Thesis(side="bull", claims=[_claim()]),
        bear=Thesis(side="bear", claims=[_claim(side="bear", evidence_ids=["EV-0001"])]),
        verdict=_verdict(),
        focus_questions=["营收增速是否可持续"],
    )
    assert report.passed is True


def test_invalid_evidence_ref_blocks():
    report = Verifier(_ledger()).check_mechanical(
        bull=Thesis(side="bull", claims=[_claim(evidence_ids=["EV-9999"])]),
        bear=Thesis(side="bear", claims=[_claim(side="bear")]),
        verdict=_verdict(),
    )
    assert report.passed is False
    assert any(issue.kind == "invalid_ref" for issue in report.issues)


def test_missing_evidence_blocks():
    claim = _claim(evidence_ids=[])
    report = Verifier(_ledger()).check_mechanical(
        bull=Thesis(side="bull", claims=[claim]),
        bear=Thesis(side="bear", claims=[_claim(side="bear")]),
        verdict=_verdict(),
    )
    assert any(issue.kind == "missing_evidence" for issue in report.issues)


def test_number_mismatch_is_warning():
    claim = _claim(statement="营收增速 99.9% 支撑估值", evidence_ids=["EV-0002"])
    report = Verifier(_ledger()).check_mechanical(
        bull=Thesis(side="bull", claims=[claim]),
        bear=Thesis(side="bear", claims=[_claim(side="bear")]),
        verdict=_verdict(),
    )
    mismatch = [issue for issue in report.issues if issue.kind == "number_mismatch"]
    assert mismatch
    assert all(issue.severity == "warning" for issue in mismatch)


def test_compliance_blocks():
    report = Verifier(_ledger()).check_mechanical(
        bull=Thesis(side="bull", claims=[_claim()]),
        bear=Thesis(side="bear", claims=[_claim(side="bear")]),
        verdict=_verdict(summary="建议买入，目标价 100 元"),
    )
    kinds = {issue.kind for issue in report.issues}
    assert "compliance" in kinds
    assert report.passed is False


def test_high_strength_claim_requires_falsifier():
    claim = _claim(strength="high")
    claim.falsifiers = []
    report = Verifier(_ledger()).check_mechanical(
        bull=Thesis(side="bull", claims=[claim]),
        bear=Thesis(side="bear", claims=[_claim(side="bear")]),
        verdict=_verdict(),
    )
    assert any(issue.kind == "missing_falsifier" for issue in report.issues)


def test_negative_evidence_requires_risks():
    ledger = _ledger()
    ledger.add(LedgerEvidence(evidence_id="", category="news", statement="公司业绩下滑，遭监管处罚"))
    ledger.add(LedgerEvidence(evidence_id="", category="news", statement="大股东减持"))
    report = Verifier(ledger).check_mechanical(
        bull=Thesis(side="bull", claims=[_claim()]),
        bear=Thesis(side="bear", claims=[_claim(side="bear")]),
        verdict=_verdict(structured_risks=[]),
    )
    assert any(issue.kind == "risk_understated" for issue in report.issues)
