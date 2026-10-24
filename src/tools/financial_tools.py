#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""财务数据工具"""

from __future__ import annotations

from typing import Any, Dict

from agents.state import AssetType
from tools.base import BaseTool, CostLevel, RiskLevel


class StockFinancialSummaryTool(BaseTool):
    name = "stock_financial_summary"
    description = "获取A股公司财务摘要：营收/归母净利及同比、经营现金流、资产负债率、商誉占比"
    timeout = 30
    asset_types = [AssetType.CN_STOCK]
    intents = ["asset_analysis", "fundamental_analysis"]
    cost_level = CostLevel.MEDIUM
    freshness_requirement_seconds = 604800
    risk_level = RiskLevel.LOW

    def execute(self, symbol: str, periods: int = 8) -> Dict[str, Any]:
        from data.financial_client import get_financial_summary
        from utils.pit import get_as_of

        try:
            periods = int(periods)
        except (TypeError, ValueError):
            periods = 8
        return get_financial_summary(symbol, periods=periods, as_of=get_as_of())


class StockFinancialIndicatorTool(BaseTool):
    name = "stock_financial_indicator"
    description = "获取A股公司财务指标时序：ROE、毛利率、净利率、资产负债率、周转率、流动比率"
    timeout = 30
    asset_types = [AssetType.CN_STOCK]
    intents = ["asset_analysis", "fundamental_analysis"]
    cost_level = CostLevel.MEDIUM
    freshness_requirement_seconds = 604800
    risk_level = RiskLevel.LOW

    def execute(self, symbol: str, periods: int = 8) -> Dict[str, Any]:
        from data.financial_client import get_financial_indicators
        from utils.pit import get_as_of

        try:
            periods = int(periods)
        except (TypeError, ValueError):
            periods = 8
        return get_financial_indicators(symbol, periods=periods, as_of=get_as_of())


class StockPeerCompareTool(BaseTool):
    name = "stock_peer_compare"
    description = "获取同行业公司的PE(TTM)/PB分位，判断目标公司估值在行业中的位置"
    timeout = 30
    asset_types = [AssetType.CN_STOCK]
    intents = ["comparison", "asset_analysis"]
    cost_level = CostLevel.MEDIUM
    risk_level = RiskLevel.LOW

    def execute(self, symbol: str, limit: int = 10) -> Dict[str, Any]:
        from data.financial_client import get_peer_compare
        from utils.pit import get_as_of

        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 10
        return get_peer_compare(symbol, limit=limit, as_of=get_as_of())
