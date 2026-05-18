#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
答案生成节点
基于证据池生成结构化投资答案
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from agent.v2.state import (
    EvidenceItem,
    EvidenceType,
    InvestmentAnswer,
    InvestmentState,
)
from services.task_service import TaskService

logger = logging.getLogger(__name__)


def draft_answer(state: InvestmentState) -> Dict[str, Any]:
    """
    生成答案初稿
    
    职责：
    - 只基于 evidence_items 生成初稿
    - 明确区分事实、推断和建议
    - 不输出最终合规免责声明
    """
    logger.info("draft_answer: 基于证据生成答案初稿")

    recommendation = ""
    for result in state.tool_results:
        if result.tool_name == "analysis" and result.status in ("success", "partial"):
            recommendation = result.data.get("recommendation", "")
            break

    if recommendation:
        draft = recommendation
    else:
        draft = _generate_evidence_based_answer(state)

    trace = state.trace + [{
        "node": "draft_answer",
        "status": "completed",
        "input_summary": f"evidence_items={len(state.evidence_items)}",
        "output_summary": f"draft_length={len(draft)}",
        "latency_ms": 0,
    }]

    TaskService.emit_event(state.task_id, "draft_created", {
        "summary": draft,
    })

    return {
        "draft_answer": draft,
        "trace": trace,
    }


def compose_answer(state: InvestmentState) -> Dict[str, Any]:
    """
    组装最终结构化答案
    
    职责：
    - 基于证据和草稿生成结构化答案
    - 包含摘要、关键点、证据引用、情景、风险、操作选项
    """
    logger.info("compose_answer: 组装结构化答案")

    evidence = state.evidence_items
    assets = state.assets

    summary = state.draft_answer or _generate_summary(evidence, assets)
    key_points = _extract_key_points(evidence)
    evidence_refs = [e.evidence_id for e in evidence[:10]]
    scenarios = _generate_scenarios(evidence, assets)
    risks = _extract_risks(evidence)
    action_options = _generate_action_options(evidence, state.user_profile)
    data_limitations = _extract_limitations(evidence)
    confidence = _calculate_confidence(evidence)

    answer = InvestmentAnswer(
        session_id=state.session_id,
        query=state.query,
        assets=assets,
        summary=summary,
        key_points=key_points,
        evidence_refs=evidence_refs,
        scenarios=scenarios,
        risks=risks,
        action_options=action_options,
        confidence=confidence,
        data_limitations=data_limitations,
    )

    formatted = _format_answer(answer)

    trace = state.trace + [{
        "node": "compose_answer",
        "status": "completed",
        "input_summary": f"evidence={len(evidence)}, assets={len(assets)}",
        "output_summary": f"answer_length={len(formatted)}, confidence={confidence:.2f}",
        "latency_ms": 0,
    }]

    return {
        "investment_answer": answer,
        "final_answer": formatted,
        "trace": trace,
    }


def _generate_evidence_based_answer(state: InvestmentState) -> str:
    """基于证据生成答案"""
    parts = [f"关于您的问题「{state.query}」，以下是基于证据的分析："]

    market_evidence = [e for e in state.evidence_items if e.evidence_type == EvidenceType.MARKET_DATA]
    if market_evidence:
        parts.append("\n**市场数据：**")
        for e in market_evidence[:3]:
            parts.append(f"- {e.title}: {e.summary}")

    news_evidence = [e for e in state.evidence_items if e.evidence_type == EvidenceType.NEWS]
    if news_evidence:
        parts.append("\n**相关新闻：**")
        for e in news_evidence[:3]:
            parts.append(f"- {e.title}")

    knowledge_evidence = [e for e in state.evidence_items if e.evidence_type == EvidenceType.RAG_KNOWLEDGE]
    if knowledge_evidence:
        parts.append("\n**知识参考：**")
        for e in knowledge_evidence[:2]:
            parts.append(f"- {e.summary[:100]}")

    analysis_evidence = [
        e for e in state.evidence_items
        if e.source == "AnalysisAgent" or e.title == "综合分析结论"
    ]
    if analysis_evidence:
        parts.append("\n**综合分析：**")
        for e in analysis_evidence[:1]:
            parts.append(f"- {e.summary[:200]}")

    if not state.evidence_items:
        parts.append("\n当前可用证据不足，建议补充行情、新闻或持仓信息后再分析。")

    return "\n".join(parts)


def _generate_summary(evidence: List[EvidenceItem], assets: list) -> str:
    """生成摘要"""
    if not evidence:
        return "暂无足够证据生成分析。"
    
    parts = []
    if assets:
        asset_names = [a.name or a.symbol for a in assets[:3] if a.name or a.symbol]
        if asset_names:
            parts.append(f"针对 {', '.join(asset_names)} 的分析")
    
    market_data = [e for e in evidence if e.evidence_type == EvidenceType.MARKET_DATA]
    if market_data:
        parts.append(f"基于 {len(market_data)} 条市场数据")
    
    return "。".join(parts) if parts else "综合分析"


def _extract_key_points(evidence: List[EvidenceItem]) -> List[str]:
    """提取关键点"""
    key_points = []
    
    high_importance = [e for e in evidence if e.importance >= 0.7]
    for e in high_importance[:5]:
        if e.summary:
            key_points.append(e.summary[:150])
    
    return key_points


def _generate_scenarios(evidence: List[EvidenceItem], assets: list) -> List[Dict[str, Any]]:
    """生成情景分析"""
    scenarios = [
        {"name": "乐观情景", "probability": 30, "content": "若市场环境向好，资产可能出现上涨。"},
        {"name": "中性情景", "probability": 40, "content": "维持当前趋势，波动在正常范围内。"},
        {"name": "悲观情景", "probability": 30, "content": "若风险因素显现，资产可能面临下行压力。"},
    ]

    positive_evidence = [e for e in evidence if e.polarity == "positive"]
    negative_evidence = [e for e in evidence if e.polarity == "negative"]

    if positive_evidence:
        scenarios[0]["content"] = f"基于 {len(positive_evidence)} 条积极信号，存在上行机会。"
    if negative_evidence:
        scenarios[2]["content"] = f"基于 {len(negative_evidence)} 条风险信号，需关注下行风险。"

    return scenarios


def _extract_risks(evidence: List[EvidenceItem]) -> List[str]:
    """提取风险"""
    risks = []
    
    negative_evidence = [e for e in evidence if e.polarity == "negative"]
    for e in negative_evidence[:3]:
        risks.append(e.summary[:100])
    
    for e in evidence:
        if e.limitations:
            risks.extend(e.limitations[:2])
    
    if not risks:
        risks.append("市场波动风险")
        risks.append("信息时效性风险")
    
    return risks[:5]


def _generate_action_options(evidence: List[EvidenceItem], user_profile: Dict[str, Any]) -> List[str]:
    """生成操作选项"""
    options = []
    
    risk_pref = user_profile.get("risk_preference", "balanced")
    
    if risk_pref == "conservative":
        options.append("保守型：建议观望，等待更多确认信号")
        options.append("稳健型：可先做跟踪观察，明确风险边界后再决策")
    elif risk_pref == "aggressive":
        options.append("激进型：可重点跟踪催化与风险变化，避免单一信号决策")
        options.append("平衡型：维持当前仓位，动态调整")
    else:
        options.append("保守型：建议观望，等待确认信号")
        options.append("平衡型：可适当关注，分批验证判断")
        options.append("激进型：若看好可提高跟踪频率，注意风险控制")
    
    return options


def _extract_limitations(evidence: List[EvidenceItem]) -> List[str]:
    """提取数据限制"""
    limitations = []
    
    for e in evidence:
        if e.limitations:
            limitations.extend(e.limitations)
    
    low_confidence = [e for e in evidence if e.confidence < 0.7]
    if low_confidence:
        limitations.append(f"有 {len(low_confidence)} 条证据置信度较低")
    
    if not limitations:
        limitations.append("数据基于公开信息，可能存在滞后")
    
    return list(set(limitations))[:5]


def _calculate_confidence(evidence: List[EvidenceItem]) -> float:
    """计算整体置信度"""
    if not evidence:
        return 0.0
    
    total_importance = sum(e.importance for e in evidence)
    if total_importance == 0:
        return 0.0
    
    weighted_confidence = sum(e.confidence * e.importance for e in evidence) / total_importance
    return min(weighted_confidence, 1.0)


def _format_answer(answer: InvestmentAnswer) -> str:
    """格式化答案为用户可读文本"""
    parts = []
    
    parts.append(f"**摘要**\n{answer.summary}")
    
    if answer.key_points:
        parts.append("\n**关键判断**")
        for i, point in enumerate(answer.key_points, 1):
            parts.append(f"{i}. {point}")
    
    if answer.evidence_refs:
        parts.append(f"\n**证据依据** (共 {len(answer.evidence_refs)} 条)")
    
    if answer.scenarios:
        parts.append("\n**情景分析**")
        for scenario in answer.scenarios:
            parts.append(f"- {scenario.get('name', '情景')}：{scenario.get('content', '')}")
    
    if answer.risks:
        parts.append("\n**主要风险**")
        for risk in answer.risks:
            parts.append(f"- {risk}")
    
    if answer.action_options:
        parts.append("\n**操作选项**")
        for option in answer.action_options:
            parts.append(f"- {option}")
    
    if answer.data_limitations:
        parts.append("\n**数据限制**")
        for limitation in answer.data_limitations:
            parts.append(f"- {limitation}")
    
    parts.append(f"\n**风险提示**\n{answer.compliance_disclaimer}")
    
    return "\n".join(parts)
