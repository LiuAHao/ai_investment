#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
资产解析规则
从用户查询中识别资产（A股、美股、ETF、基金等），支持追问继承与名称搜索。
由旧 agent/v2/asset_resolver.py 迁移而来，供 AssetResolveTool 封装。
"""

from __future__ import annotations

import logging
import re
from typing import List, Optional

from agents.state import Asset, AssetResolveInput, AssetResolveResult, AssetType

logger = logging.getLogger(__name__)

US_STOCK_PATTERN = r'\b([A-Z]{1,5})\b'
HK_STOCK_PATTERN = r'\b(?:HK|hk)(\d{5})\b|\b(\d{5})\.HK\b'
CN_STOCK_PATTERN = r'(?<!\d)(\d{6})(?!\d)'

KNOWN_US_TICKERS = {"AAPL", "TSLA", "NVDA", "MSFT", "GOOGL", "AMZN", "META", "NFLX", "AMD", "INTC"}


def resolve_assets(input_data: AssetResolveInput) -> AssetResolveResult:
    """资产解析入口"""
    query = input_data.query or ""

    # 追问继承
    if input_data.intent and input_data.intent.primary_intent == "follow_up":
        if input_data.previous_assets:
            return AssetResolveResult(
                selected_assets=input_data.previous_assets,
                reason="追问继承上一轮资产",
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
        return AssetResolveResult(selected_assets=assets, reason="成功识别资产")

    return AssetResolveResult(reason="未识别到资产")


def _extract_assets_from_query(query: str) -> List[Asset]:
    """从查询中提取资产"""
    assets: List[Asset] = []

    us_matches = re.findall(US_STOCK_PATTERN, query)
    for ticker in us_matches:
        if ticker in KNOWN_US_TICKERS:
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
    if code[:2] in etf_prefixes and "ETF" in query:
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
