#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
证据处理节点
将 ToolResult 转换为 EvidenceItem，实现证据池管理
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from agent.v2.state import (
    EvidenceItem,
    EvidenceType,
    InvestmentState,
    Polarity,
    ToolResult,
)
from services.task_service import TaskService

logger = logging.getLogger(__name__)


def collect_evidence(state: InvestmentState) -> Dict[str, Any]:
    """
    收集证据
    
    职责：
    - 将 ToolResult 转换为 EvidenceItem
    - 对证据排序
    - 判断证据是否足够
    """
    logger.info("collect_evidence: 收集证据")

    evidence_items = []
    
    for result in state.tool_results:
        if result.status in ("success", "partial"):
            items = _convert_tool_result_to_evidence(result)
            evidence_items.extend(items)

    ranked_evidence = _rank_evidence(evidence_items)

    for evidence in ranked_evidence:
        TaskService.emit_event(state.task_id, "evidence_added", {
            "evidence": evidence.model_dump(mode="json") if hasattr(evidence, "model_dump") else evidence,
        })

    trace = state.trace + [{
        "node": "collect_evidence",
        "status": "completed",
        "input_summary": f"tool_results={len(state.tool_results)}",
        "output_summary": f"evidence_items={len(ranked_evidence)}",
        "latency_ms": 0,
    }]

    return {
        "evidence_items": ranked_evidence,
        "trace": trace,
    }


def _convert_tool_result_to_evidence(result: ToolResult) -> List[EvidenceItem]:
    """将工具结果转换为证据项"""
    items = []
    
    if result.tool_name in ("cn_stock_history", "cn_stock_spot_search"):
        items.extend(_extract_market_data_evidence(result))
    elif result.tool_name in ("us_stock_quote", "us_stock_history"):
        items.extend(_extract_us_stock_evidence(result))
    elif result.tool_name in ("etf_profile", "etf_tracking_index"):
        items.extend(_extract_etf_evidence(result))
    elif result.tool_name in ("fund_profile", "fund_nav_history"):
        items.extend(_extract_fund_evidence(result))
    elif result.tool_name == "asset_news_search":
        items.extend(_extract_news_evidence(result))
    elif result.tool_name == "investment_framework_search":
        items.extend(_extract_knowledge_evidence(result))
    elif result.tool_name == "analysis":
        items.extend(_extract_analysis_evidence(result))
    
    return items


def _extract_market_data_evidence(result: ToolResult) -> List[EvidenceItem]:
    """提取市场数据证据"""
    items = []
    data = result.data
    
    summary = data.get("summary", {})
    if summary:
        symbol = summary.get("symbol", "")
        close = summary.get("latest_close")
        change = summary.get("latest_change_pct")
        high = summary.get("high_max")
        low = summary.get("low_min")
        volatility = summary.get("volatility_pct")
        
        title = f"{symbol} 近期价格与波动"
        parts = []
        if close is not None:
            parts.append(f"最新收盘价 ¥{close:.2f}")
        if change is not None:
            sign = "+" if change >= 0 else ""
            parts.append(f"区间涨跌 {sign}{change:.2f}%")
        if high is not None and low is not None:
            parts.append(f"价格区间 ¥{low:.2f} ~ ¥{high:.2f}")
        if volatility is not None:
            parts.append(f"波动率 {volatility:.2f}%")
        
        items.append(EvidenceItem(
            evidence_type=EvidenceType.MARKET_DATA,
            asset_id=result.asset_id,
            title=title,
            summary="；".join(parts) if parts else "市场数据",
            raw=summary,
            source="AKShare/东方财富",
            confidence=0.9,
            importance=0.8,
            polarity=_assess_polarity(change),
        ))
    
    technical = data.get("technical", {})
    if technical:
        trend = technical.get("trend")
        momentum = technical.get("momentum_pct")
        
        if trend or momentum is not None:
            parts = []
            if trend:
                parts.append(f"趋势: {trend}")
            if momentum is not None:
                parts.append(f"动量: {momentum:+.2f}%")
            
            items.append(EvidenceItem(
                evidence_type=EvidenceType.TECHNICAL_INDICATOR,
                asset_id=result.asset_id,
                title=f"{data.get('symbol', '')} 技术指标",
                summary="；".join(parts),
                raw=technical,
                source="AKShare",
                confidence=0.85,
                importance=0.7,
            ))
    
    return items


def _extract_us_stock_evidence(result: ToolResult) -> List[EvidenceItem]:
    """提取美股数据证据"""
    items = []
    data = result.data
    
    quote = data.get("quote", {})
    if quote:
        items.append(EvidenceItem(
            evidence_type=EvidenceType.MARKET_DATA,
            asset_id=result.asset_id,
            title=f"{data.get('symbol', '')} 美股行情",
            summary="美股实时行情数据",
            raw=quote,
            source="AKShare",
            confidence=0.9,
            importance=0.8,
        ))
    
    history = data.get("history", [])
    if history:
        items.append(EvidenceItem(
            evidence_type=EvidenceType.MARKET_DATA,
            asset_id=result.asset_id,
            title=f"{data.get('symbol', '')} 历史数据",
            summary=f"近 {len(history)} 个交易日历史数据",
            raw={"history_count": len(history)},
            source="AKShare",
            confidence=0.9,
            importance=0.7,
        ))
    
    return items


def _extract_etf_evidence(result: ToolResult) -> List[EvidenceItem]:
    """提取ETF数据证据"""
    items = []
    data = result.data
    
    profile = data.get("profile", {})
    if profile:
        items.append(EvidenceItem(
            evidence_type=EvidenceType.MARKET_DATA,
            asset_id=result.asset_id,
            title=f"{data.get('symbol', '')} ETF信息",
            summary="ETF基本信息和规模数据",
            raw=profile,
            source="AKShare",
            confidence=0.9,
            importance=0.7,
        ))
    
    tracking_index = data.get("tracking_index")
    index_name = data.get("index_name")
    if tracking_index:
        items.append(EvidenceItem(
            evidence_type=EvidenceType.FUNDAMENTAL,
            asset_id=result.asset_id,
            title=f"{data.get('symbol', '')} 跟踪指数",
            summary=f"跟踪指数: {tracking_index} ({index_name or ''})",
            raw={"tracking_index": tracking_index, "index_name": index_name},
            source="资产主数据",
            confidence=1.0,
            importance=0.6,
        ))
    
    return items


def _extract_fund_evidence(result: ToolResult) -> List[EvidenceItem]:
    """提取基金数据证据"""
    items = []
    data = result.data
    
    profile = data.get("profile", {})
    if profile:
        items.append(EvidenceItem(
            evidence_type=EvidenceType.FUNDAMENTAL,
            asset_id=result.asset_id,
            title=f"{data.get('fund_code', '')} 基金信息",
            summary="基金基本信息",
            raw=profile,
            source="天天基金",
            confidence=0.85,
            importance=0.7,
        ))
    
    nav_data = data.get("nav_data", [])
    if nav_data:
        items.append(EvidenceItem(
            evidence_type=EvidenceType.MARKET_DATA,
            asset_id=result.asset_id,
            title=f"{data.get('fund_code', '')} 净值数据",
            summary=f"近 {len(nav_data)} 日净值数据",
            raw={"nav_count": len(nav_data)},
            source="天天基金",
            confidence=0.9,
            importance=0.6,
        ))
    
    return items


def _extract_news_evidence(result: ToolResult) -> List[EvidenceItem]:
    """提取新闻证据"""
    items = []
    data = result.data
    
    relevant_titles = data.get("relevant_titles", [])
    web_results = data.get("web_results", [])
    
    for i, title_info in enumerate(relevant_titles[:5]):
        if isinstance(title_info, dict):
            title = title_info.get("title", "")
            source = title_info.get("source", "")
        else:
            title = str(title_info)
            source = "新闻"
        
        if title:
            items.append(EvidenceItem(
                evidence_type=EvidenceType.NEWS,
                title=title[:100],
                summary=title,
                raw=title_info if isinstance(title_info, dict) else {"title": title},
                source=source or "新闻聚合",
                confidence=0.7,
                importance=0.6 - i * 0.1,
            ))
    
    for i, result_info in enumerate(web_results[:3]):
        title = result_info.get("title", "")
        url = result_info.get("url") or result_info.get("link") or result_info.get("href") or ""
        snippet = result_info.get("snippet") or result_info.get("body") or title
        if title:
            items.append(EvidenceItem(
                evidence_type=EvidenceType.NEWS,
                title=title[:100],
                summary=snippet,
                raw=result_info,
                source="网络搜索",
                source_url=url,
                confidence=0.6,
                importance=0.5 - i * 0.1,
            ))
    
    return items


def _extract_knowledge_evidence(result: ToolResult) -> List[EvidenceItem]:
    """提取知识库证据"""
    items = []
    data = result.data
    
    results = data.get("results", [])
    citations = data.get("citations", [])
    
    for i, res in enumerate(results[:3]):
        content = (
            res.get("content")
            or res.get("text")
            or res.get("summary")
            or ""
        ) if isinstance(res, dict) else str(res)
        if content:
            citation = citations[i] if i < len(citations) and isinstance(citations[i], dict) else {}
            items.append(EvidenceItem(
                evidence_type=EvidenceType.RAG_KNOWLEDGE,
                title=citation.get("title") or f"知识库参考 {i+1}",
                summary=content[:200],
                raw=res if isinstance(res, dict) else {"content": content},
                source=citation.get("source") or "知识库",
                confidence=0.8,
                importance=0.5 - i * 0.1,
            ))
    
    return items


def _extract_analysis_evidence(result: ToolResult) -> List[EvidenceItem]:
    """提取分析结果证据"""
    items = []
    data = result.data
    
    recommendation = data.get("recommendation", "")
    if recommendation:
        items.append(EvidenceItem(
            evidence_type=EvidenceType.FUNDAMENTAL,
            title="综合分析结论",
            summary=recommendation[:300],
            raw={"recommendation": recommendation},
            source="AnalysisAgent",
            confidence=0.85,
            importance=0.9,
        ))
    
    return items


def _assess_polarity(change_pct: Optional[float]) -> Optional[Polarity]:
    """评估情感极性"""
    if change_pct is None:
        return None
    if change_pct > 1:
        return Polarity.POSITIVE
    elif change_pct < -1:
        return Polarity.NEGATIVE
    else:
        return Polarity.NEUTRAL


def _rank_evidence(evidence_items: List[EvidenceItem]) -> List[EvidenceItem]:
    """
    证据排序
    
    综合分 = 相关性 * 0.35
          + 新鲜度 * 0.20
          + 置信度 * 0.20
          + 来源可靠性 * 0.15
          + 重要性 * 0.10
    """
    def calculate_score(item: EvidenceItem) -> float:
        relevance = item.relevance_score
        freshness = _calculate_freshness(item)
        confidence = item.confidence
        source_reliability = _get_source_reliability(item.source)
        importance = item.importance
        
        return (
            relevance * 0.35 +
            freshness * 0.20 +
            confidence * 0.20 +
            source_reliability * 0.15 +
            importance * 0.10
        )
    
    scored_items = [(calculate_score(item), item) for item in evidence_items]
    scored_items.sort(key=lambda x: x[0], reverse=True)
    
    return [item for _, item in scored_items]


def _calculate_freshness(item: EvidenceItem) -> float:
    """计算新鲜度分数"""
    if not item.observed_at:
        return 0.5
    
    try:
        age_seconds = (datetime.now() - item.observed_at).total_seconds()
        if age_seconds < 3600:
            return 1.0
        elif age_seconds < 86400:
            return 0.8
        elif age_seconds < 604800:
            return 0.6
        else:
            return 0.4
    except Exception:
        return 0.5


def _get_source_reliability(source: str) -> float:
    """获取来源可靠性分数"""
    reliability_map = {
        "AKShare": 0.9,
        "东方财富": 0.9,
        "天天基金": 0.85,
        "知识库": 0.8,
        "新闻聚合": 0.7,
        "网络搜索": 0.6,
        "AnalysisAgent": 0.85,
    }
    return reliability_map.get(source, 0.5)
