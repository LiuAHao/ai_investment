#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
股票数据工具
封装 V1 DataAgent 的功能
"""

from __future__ import annotations

from typing import Any, Dict, List

from agent.v2.state import AssetType
from tools.base import BaseTool, CostLevel, RiskLevel


class StockDataTool(BaseTool):
    """A股历史数据和技术指标工具"""

    name = "cn_stock_history"
    description = "获取A股历史行情和技术指标"
    timeout = 20

    asset_types = [AssetType.CN_STOCK]
    intents = ["asset_analysis", "risk_check", "comparison"]
    cost_level = CostLevel.MEDIUM
    freshness_requirement_seconds = 86400
    fallback_tools = ["cn_stock_spot_search"]
    risk_level = RiskLevel.LOW

    def execute(self, symbol: str, **kwargs) -> Dict[str, Any]:
        from agent.data_agent import DataAgent
        agent = DataAgent()
        summary = agent.analyze_daily_hist(symbol=symbol)
        technical = agent.analyze_technical_indicators(symbol=symbol)
        return {"symbol": symbol, "summary": summary, "technical": technical}


class StockSpotTool(BaseTool):
    """A股实时行情搜索工具"""

    name = "cn_stock_spot_search"
    description = "搜索A股实时行情数据"
    timeout = 15

    asset_types = [AssetType.CN_STOCK]
    intents = ["asset_analysis", "market_overview"]
    cost_level = CostLevel.LOW
    freshness_requirement_seconds = 900
    risk_level = RiskLevel.LOW

    def execute(self, symbols: List[str], limit: int = 30, **kwargs) -> Dict[str, Any]:
        from agent.data_agent import DataAgent
        agent = DataAgent()
        return agent.fetch_spot_em(symbols=symbols, limit=limit)
