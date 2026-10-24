#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""宏观与指数环境工具"""

from __future__ import annotations

from typing import Any, Dict

from agents.state import AssetType
from tools.base import BaseTool, CostLevel, RiskLevel


class MacroIndicatorTool(BaseTool):
    name = "macro_indicator"
    description = "获取宏观指标：PMI、CPI、Shibor、LPR 的最近若干期数值"
    timeout = 30
    asset_types = [AssetType.MACRO, AssetType.INDEX]
    intents = ["macro_analysis", "market_overview"]
    cost_level = CostLevel.LOW
    risk_level = RiskLevel.LOW

    def execute(self, months: int = 12) -> Dict[str, Any]:
        from data.macro_client import get_macro_indicators
        from utils.pit import get_as_of

        try:
            months = int(months)
        except (TypeError, ValueError):
            months = 12
        return get_macro_indicators(months=months, as_of=get_as_of())


class IndexEnvironmentTool(BaseTool):
    name = "index_environment"
    description = "获取上证/深证/创业板/沪深300 指数点位与近20/60日涨跌幅、成交额"
    timeout = 30
    asset_types = [AssetType.INDEX, AssetType.CN_STOCK, AssetType.ETF, AssetType.FUND]
    intents = ["market_overview", "asset_analysis"]
    cost_level = CostLevel.LOW
    freshness_requirement_seconds = 86400
    risk_level = RiskLevel.LOW

    def execute(self) -> Dict[str, Any]:
        from data.macro_client import get_index_environment
        from utils.pit import get_as_of

        return get_index_environment(as_of=get_as_of())
