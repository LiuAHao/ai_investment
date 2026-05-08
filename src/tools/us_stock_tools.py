#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
美股工具
提供美股行情数据
"""

from __future__ import annotations

from typing import Any, Dict

from agent.v2.state import AssetType
from tools.base import BaseTool, CostLevel, RiskLevel


class UsStockQuoteTool(BaseTool):
    """美股实时行情工具"""

    name = "us_stock_quote"
    description = "获取美股实时行情"
    timeout = 15

    asset_types = [AssetType.US_STOCK]
    intents = ["asset_analysis", "market_overview"]
    cost_level = CostLevel.LOW
    freshness_requirement_seconds = 900
    risk_level = RiskLevel.LOW

    def execute(self, symbol: str, **kwargs) -> Dict[str, Any]:
        """获取美股实时行情"""
        try:
            import akshare as ak
            df = ak.stock_us_spot_em()
            if df is not None and not df.empty:
                row = df[df["代码"].str.contains(symbol, case=False, na=False)]
                if not row.empty:
                    data = row.iloc[0].to_dict()
                    return {"symbol": symbol, "quote": data}
        except Exception as e:
            pass
        return {"symbol": symbol, "quote": {}, "note": "美股行情数据暂不可用"}


class UsStockHistoryTool(BaseTool):
    """美股历史数据工具"""

    name = "us_stock_history"
    description = "获取美股历史行情数据"
    timeout = 20

    asset_types = [AssetType.US_STOCK]
    intents = ["asset_analysis", "risk_check"]
    cost_level = CostLevel.MEDIUM
    freshness_requirement_seconds = 86400
    risk_level = RiskLevel.LOW

    def execute(self, symbol: str, period: str = "daily", **kwargs) -> Dict[str, Any]:
        """获取美股历史数据"""
        try:
            import akshare as ak
            df = ak.stock_us_daily(symbol=symbol, adjust="qfq")
            if df is not None and not df.empty:
                data = df.tail(30).to_dict(orient="records")
                return {"symbol": symbol, "history": data}
        except Exception as e:
            pass
        return {"symbol": symbol, "history": [], "note": "美股历史数据暂不可用"}
