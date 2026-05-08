#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
V2 证据池、回答生成和连续追问记忆测试
"""

import os
import sys
from datetime import datetime

CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_SRC = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
if PROJECT_SRC not in sys.path:
    sys.path.insert(0, PROJECT_SRC)

from agent.v2.answer_agent import compose_answer, draft_answer
from agent.v2.asset_resolver import resolve_assets
from agent.v2.evidence_agent import collect_evidence
from agent.v2.memory_agent import _build_evidence_record, _extract_key_assumptions
from agent.v2.state import (
    Asset,
    AssetType,
    EvidenceItem,
    EvidenceType,
    IntentResult,
    InvestmentState,
    Polarity,
    ResearchContext,
    ToolResult,
)


def test_collect_evidence_extracts_market_news_and_rag_items():
    """ToolResult 应被转换为行情、新闻和 RAG 证据"""
    state = InvestmentState(
        session_id="s-evidence",
        user_id=1,
        query="分析宁德时代",
        tool_results=[
            ToolResult(
                tool_name="cn_stock_history",
                status="success",
                asset_id="cn_stock:300750",
                data={
                    "symbol": "300750",
                    "summary": {
                        "symbol": "300750",
                        "latest_close": 100.0,
                        "latest_change_pct": 2.5,
                        "high_max": 110.0,
                        "low_min": 90.0,
                    },
                    "technical": {"trend": "上行", "momentum_pct": 3.2},
                },
            ),
            ToolResult(
                tool_name="asset_news_search",
                status="success",
                data={
                    "relevant_titles": ["宁德时代发布新产品"],
                    "web_results": [{"title": "行业新闻", "link": "https://example.com", "snippet": "新能源新闻"}],
                },
            ),
            ToolResult(
                tool_name="investment_framework_search",
                status="success",
                data={
                    "results": [{"text": "成长股需要关注估值、景气度和现金流。"}],
                    "citations": [{"title": "估值框架", "source": "知识库"}],
                },
            ),
        ],
    )

    result = collect_evidence(state)
    evidence = result["evidence_items"]
    evidence_types = {item.evidence_type for item in evidence}

    assert EvidenceType.MARKET_DATA in evidence_types
    assert EvidenceType.TECHNICAL_INDICATOR in evidence_types
    assert EvidenceType.NEWS in evidence_types
    assert EvidenceType.RAG_KNOWLEDGE in evidence_types
    assert any(item.source_url == "https://example.com" for item in evidence)
    assert any("成长股" in item.summary for item in evidence)


def test_answer_generation_uses_evidence_and_outputs_structured_answer():
    """回答链路应基于证据生成结构化答案和用户可读文本"""
    evidence = [
        EvidenceItem(
            evidence_type=EvidenceType.MARKET_DATA,
            asset_id="cn_stock:300750",
            title="300750 近期价格与波动",
            summary="最新收盘价 ¥100.00；区间涨跌 +2.50%",
            source="AKShare",
            confidence=0.9,
            importance=0.8,
            polarity=Polarity.POSITIVE,
        ),
        EvidenceItem(
            evidence_type=EvidenceType.NEWS,
            title="行业竞争加剧",
            summary="行业竞争可能影响利润率",
            source="网络搜索",
            confidence=0.6,
            importance=0.6,
            polarity=Polarity.NEGATIVE,
            limitations=["新闻来源需要进一步确认"],
        ),
    ]
    state = InvestmentState(
        session_id="s-answer",
        user_id=1,
        query="分析宁德时代",
        assets=[
            Asset(
                asset_id="cn_stock:300750",
                asset_type=AssetType.CN_STOCK,
                symbol="300750",
                name="宁德时代",
            )
        ],
        evidence_items=evidence,
        user_profile={"risk_preference": "conservative"},
    )

    draft_result = draft_answer(state)
    state.draft_answer = draft_result["draft_answer"]
    composed = compose_answer(state)

    assert "市场数据" in state.draft_answer
    assert composed["investment_answer"].evidence_refs
    assert composed["investment_answer"].confidence > 0
    assert "证据依据" in composed["final_answer"]
    assert "风险提示" in composed["final_answer"]


def test_follow_up_asset_resolution_uses_research_context():
    """追问应从 research_context 继承上一轮资产"""
    previous_asset = Asset(
        asset_id="cn_stock:300750",
        asset_type=AssetType.CN_STOCK,
        symbol="300750",
        name="宁德时代",
    )
    state = InvestmentState(
        session_id="s-follow",
        user_id=1,
        query="那如果持有三个月呢",
        intent=IntentResult(primary_intent="follow_up"),
        research_context=ResearchContext(
            session_id="s-follow",
            user_id=1,
            current_assets=[previous_asset],
        ),
    )

    result = resolve_assets(state)

    assert result["assets"] == [previous_asset]
    assert not result["ambiguous_assets"]


def test_key_assumptions_use_asset_bound_evidence():
    """关键假设应基于带 asset_id 的证据提取"""
    asset = Asset(
        asset_id="cn_stock:300750",
        asset_type=AssetType.CN_STOCK,
        symbol="300750",
        name="宁德时代",
    )
    state = InvestmentState(
        session_id="s-memory",
        user_id=1,
        query="分析宁德时代",
        assets=[asset],
        evidence_items=[
            EvidenceItem(
                evidence_type=EvidenceType.MARKET_DATA,
                asset_id="cn_stock:300750",
                title="行情证据",
                summary="近期市场数据",
                source="AKShare",
            ),
            EvidenceItem(
                evidence_type=EvidenceType.NEWS,
                asset_id="cn_stock:300750",
                title="新闻证据",
                summary="近期新闻",
                source="网络搜索",
            ),
        ],
    )

    assumptions = _extract_key_assumptions(state)

    assert assumptions
    assert assumptions[0]["asset_id"] == "cn_stock:300750"
    assert "基于近期市场数据分析" in assumptions[0]["assumptions"]
    assert "考虑了近期新闻事件影响" in assumptions[0]["assumptions"]


def test_build_evidence_record_maps_all_fields():
    """证据入库记录应保留核心字段"""
    evidence = EvidenceItem(
        evidence_id="e-test",
        evidence_type=EvidenceType.NEWS,
        asset_id="cn_stock:300750",
        title="测试新闻",
        summary="新闻摘要",
        raw={"title": "测试新闻"},
        source="网络搜索",
        source_url="https://example.com",
        observed_at=datetime(2026, 5, 8),
        confidence=0.7,
        importance=0.6,
        polarity=Polarity.NEGATIVE,
        limitations=["来源需确认"],
    )
    state = InvestmentState(session_id="s-record", user_id=7, query="分析")

    record = _build_evidence_record(state, evidence)

    assert record.evidence_id == "e-test"
    assert record.session_id == "s-record"
    assert record.user_id == 7
    assert record.asset_id == "cn_stock:300750"
    assert record.evidence_type == "news"
    assert record.polarity == "negative"
    assert "来源需确认" in record.limitations_json
