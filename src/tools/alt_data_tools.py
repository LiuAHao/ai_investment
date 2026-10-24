#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
扩展数据工具（全部基于 tushare，无第三方爬虫）

- stock_fund_flow：主力资金 / 两融 / 北向 / 股东户数
- stock_expectation：业绩预告 / 快报 / 预约披露
- stock_valuation_band：PE/PB/PS/股息率历史分位
- stock_events：分红 / 解禁
- industry_context：行业相对强弱与估值中位数
- hk_stock_history：港股日线
"""

from __future__ import annotations

from typing import Any, Dict

from agents.state import AssetType
from tools.base import BaseTool, CostLevel, RiskLevel
from utils.pit import get_as_of


class StockFundFlowTool(BaseTool):
    """资金行为工具"""

    name = "stock_fund_flow"
    description = "获取个股资金行为：主力净流入、融资余额、北向资金、股东户数"
    timeout = 30

    asset_types = [AssetType.CN_STOCK]
    intents = ["asset_analysis", "risk_check", "market_overview"]
    cost_level = CostLevel.MEDIUM
    freshness_requirement_seconds = 86400
    risk_level = RiskLevel.LOW

    def execute(self, symbol: str, days: int = 30) -> Dict[str, Any]:
        from data.alt_data import get_fund_flow

        return get_fund_flow(symbol, days=int(days or 30), as_of=get_as_of())


class StockExpectationTool(BaseTool):
    """预期与事件工具"""

    name = "stock_expectation"
    description = "获取业绩预告、业绩快报与财报预约披露日，用于判断预期差"
    timeout = 25

    asset_types = [AssetType.CN_STOCK]
    intents = ["asset_analysis", "event_analysis"]
    cost_level = CostLevel.LOW
    freshness_requirement_seconds = 86400
    risk_level = RiskLevel.LOW

    def execute(self, symbol: str) -> Dict[str, Any]:
        from data.alt_data import get_expectations

        return get_expectations(symbol, as_of=get_as_of())


class StockValuationBandTool(BaseTool):
    """估值历史分位工具"""

    name = "stock_valuation_band"
    description = "获取 PE(TTM)/PB/PS/股息率的历史分位（默认近 5 年）"
    timeout = 30

    asset_types = [AssetType.CN_STOCK]
    intents = ["asset_analysis", "comparison"]
    cost_level = CostLevel.MEDIUM
    freshness_requirement_seconds = 86400
    risk_level = RiskLevel.LOW

    def execute(self, symbol: str, years: int = 5) -> Dict[str, Any]:
        from data.alt_data import get_valuation_band

        return get_valuation_band(symbol, years=int(years or 5), as_of=get_as_of())


class StockEventsTool(BaseTool):
    """公司事件工具"""

    name = "stock_events"
    description = "获取分红与限售解禁事件"
    timeout = 20

    asset_types = [AssetType.CN_STOCK]
    intents = ["asset_analysis", "event_analysis", "risk_check"]
    cost_level = CostLevel.LOW
    freshness_requirement_seconds = 86400
    risk_level = RiskLevel.LOW

    def execute(self, symbol: str) -> Dict[str, Any]:
        from data.alt_data import get_events

        return get_events(symbol, as_of=get_as_of())


class IndustryContextTool(BaseTool):
    """行业相对强弱工具"""

    name = "industry_context"
    description = "获取行业等权涨幅、目标股排名与行业估值中位数"
    timeout = 35

    asset_types = [AssetType.CN_STOCK, AssetType.INDUSTRY]
    intents = ["asset_analysis", "market_overview", "comparison"]
    cost_level = CostLevel.MEDIUM
    freshness_requirement_seconds = 86400
    risk_level = RiskLevel.LOW

    def execute(self, symbol: str) -> Dict[str, Any]:
        from data.alt_data import get_industry_context

        return get_industry_context(symbol, as_of=get_as_of())


class HkStockHistoryTool(BaseTool):
    """港股日线工具"""

    name = "hk_stock_history"
    description = "获取港股历史日线（最近 60 个交易日；tushare 限 5 次/天，仅建议手动低频使用）"
    timeout = 20

    asset_types = [AssetType.HK_STOCK]
    intents = ["asset_analysis", "risk_check"]
    cost_level = CostLevel.LOW
    freshness_requirement_seconds = 86400
    risk_level = RiskLevel.LOW

    def execute(self, symbol: str, days: int = 60) -> Dict[str, Any]:
        from data.alt_data import get_hk_history

        return get_hk_history(symbol, days=int(days or 60), as_of=get_as_of())
