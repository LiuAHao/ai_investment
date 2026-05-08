#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
资产解析节点
识别用户提到的资产，支持多资产类型
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from agent.v2.state import (
    Asset,
    AssetResolveInput,
    AssetResolveResult,
    AssetType,
    InvestmentState,
)

logger = logging.getLogger(__name__)

US_STOCK_PATTERN = r'\b([A-Z]{1,5})\b'
HK_STOCK_PATTERN = r'\b(?:HK|hk)(\d{5})\b|\b(\d{5})\.HK\b'
CN_STOCK_PATTERN = r'(?<!\d)(\d{6})(?!\d)'
FUND_PATTERN = r'\b(\d{6})\b(?:基金|fund)'


def resolve_assets(state: InvestmentState) -> Dict[str, Any]:
    """
    资产解析
    
    职责：
    - 识别资产（A股、美股、ETF、基金等）
    - 对追问继承上一轮资产
    - 对歧义资产给出候选
    """
    logger.info("resolve_assets: 解析资产, query=%s", state.query[:50])

    if state.intent and state.intent.primary_intent == "knowledge_query":
        trace = state.trace + [{
            "node": "resolve_assets",
            "status": "skipped",
            "input_summary": "knowledge_query, skip asset resolution",
            "output_summary": "no assets needed",
            "latency_ms": 0,
        }]
        return {"assets": [], "trace": trace}

    input_data = AssetResolveInput(
        query=state.query,
        chat_history=state.chat_history,
        previous_assets=state.assets or (state.research_context.current_assets if state.research_context else []),
        intent=state.intent,
    )

    result = _resolve_assets_internal(input_data)

    assets = result.selected_assets
    candidates = result.candidates
    ambiguous = result.ambiguous

    if result.need_user_clarification and candidates:
        logger.info("需要用户澄清，候选资产: %s", [c.name for c in candidates])

    trace = state.trace + [{
        "node": "resolve_assets",
        "status": "completed",
        "input_summary": f"query={state.query[:50]}",
        "output_summary": f"found {len(assets)} assets, ambiguous={ambiguous}, candidates={len(candidates)}",
        "latency_ms": 0,
    }]

    return {
        "assets": assets,
        "asset_candidates": candidates,
        "ambiguous_assets": ambiguous,
        "trace": trace,
    }


def _resolve_assets_internal(input_data: AssetResolveInput) -> AssetResolveResult:
    """内部资产解析逻辑"""
    query = input_data.query

    if input_data.intent and input_data.intent.primary_intent == "follow_up":
        if input_data.previous_assets:
            if len(input_data.previous_assets) == 1:
                return AssetResolveResult(
                    selected_assets=input_data.previous_assets,
                    reason="追问继承上一轮资产",
                )
            else:
                return AssetResolveResult(
                    selected_assets=input_data.previous_assets,
                    reason="追问继承上一轮多个资产",
                )

    assets = _extract_assets_from_query(query)

    if not assets:
        assets = _search_by_name(query)

    if len(assets) > 1:
        unique_types = set(a.asset_type for a in assets)
        is_comparison = (
            input_data.intent is not None
            and input_data.intent.primary_intent in {"comparison", "asset_compare"}
        )
        if len(unique_types) > 1 or not is_comparison:
            return AssetResolveResult(
                candidates=assets,
                ambiguous=True,
                need_user_clarification=True,
                reason="识别到多个可能资产，需要用户澄清",
            )

    if assets:
        return AssetResolveResult(
            selected_assets=assets,
            reason="成功识别资产",
        )

    return AssetResolveResult(reason="未识别到资产")


def _extract_assets_from_query(query: str) -> List[Asset]:
    """从查询中提取资产"""
    assets = []

    us_matches = re.findall(US_STOCK_PATTERN, query)
    known_us_tickers = {"AAPL", "TSLA", "NVDA", "MSFT", "GOOGL", "AMZN", "META", "NFLX", "AMD", "INTC"}
    for ticker in us_matches:
        if ticker in known_us_tickers:
            assets.append(Asset(
                asset_id=f"us_stock:{ticker}",
                asset_type=AssetType.US_STOCK,
                symbol=ticker,
                market="US",
                exchange="NASDAQ",
                currency="USD",
                confidence=0.95,
            ))

    hk_matches = re.findall(HK_STOCK_PATTERN, query)
    for match in hk_matches:
        code = next((part for part in match if part), "")
        if not code:
            continue
        assets.append(Asset(
            asset_id=f"hk_stock:{code}",
            asset_type=AssetType.HK_STOCK,
            symbol=code,
            market="HK",
            exchange="HKEX",
            currency="HKD",
            confidence=0.9,
        ))

    cn_matches = re.findall(CN_STOCK_PATTERN, query)
    for code in cn_matches:
        if code.startswith(("6", "0", "3")):
            asset_type = _guess_cn_asset_type(code, query)
            exchange = "SSE" if code.startswith("6") else "SZSE"
            assets.append(Asset(
                asset_id=f"{asset_type.value}:{code}",
                asset_type=asset_type,
                symbol=code,
                market="CN",
                exchange=exchange,
                currency="CNY",
                confidence=0.9,
            ))

    return assets


def _guess_cn_asset_type(code: str, query: str) -> AssetType:
    """猜测中国资产类型"""
    etf_prefixes = ("51", "15", "16")
    if code[:2] in etf_prefixes and ("ETF" in query or "etf" in query or "ETF" in query):
        return AssetType.ETF

    if "基金" in query or "fund" in query.lower():
        return AssetType.FUND

    return AssetType.CN_STOCK


def _search_by_name(query: str) -> List[Asset]:
    """通过名称搜索资产"""
    try:
        from asset import get_asset_master
        master = get_asset_master()
        results = master.search(query, limit=8)
        if not results:
            return []

        query_upper = query.upper()
        if "ETF" in query_upper:
            etf_results = [item for item in results if item.asset_type == AssetType.ETF]
            if etf_results:
                return etf_results[:5]
        if "基金" in query or "FUND" in query_upper:
            fund_results = [item for item in results if item.asset_type == AssetType.FUND]
            if fund_results:
                return fund_results[:5]

        best_score = max(item.confidence for item in results)
        if best_score >= 0.9:
            return [item for item in results if item.confidence >= best_score]
        return results[:5]
    except Exception as e:
        logger.warning("名称搜索失败: %s", e)
        return []


def _guess_market(code: str) -> str:
    """根据代码猜测市场"""
    if code.startswith("6"):
        return "SH"
    elif code.startswith(("0", "3")):
        return "SZ"
    elif code.startswith("8"):
        return "BJ"
    return "Unknown"


def _extract_name_candidates(text: str) -> List[str]:
    """提取可能的公司名"""
    stopwords = {"分析", "财报", "走势", "后期", "影响", "今天", "今日", "复盘", "建议", "风险"}
    terms = re.findall(r"[\u4e00-\u9fa5]{2,8}", text or "")
    candidates = []
    for term in terms:
        if term not in stopwords and not any(sw in term for sw in stopwords):
            if term not in candidates:
                candidates.append(term)
    return candidates[:5]
