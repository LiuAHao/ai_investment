#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
美股工具
提供美股日线数据（Alpaca Data API v2）。

密钥从环境变量读取，不写入日志或返回值。
"""

from __future__ import annotations

from typing import Any, Dict

from agents.state import AssetType
from tools.base import BaseTool, CostLevel, RiskLevel


class UsStockHistoryTool(BaseTool):
    """美股历史数据工具"""

    name = "us_stock_history"
    description = "获取美股历史行情数据（日线，最近 30 个交易日）"
    timeout = 20

    asset_types = [AssetType.US_STOCK]
    intents = ["asset_analysis", "risk_check"]
    cost_level = CostLevel.MEDIUM
    freshness_requirement_seconds = 86400
    risk_level = RiskLevel.LOW

    def execute(self, symbol: str, period: str = "daily", **kwargs) -> Dict[str, Any]:
        """获取美股日线（Alpaca Data API，默认前复权）"""
        from data.us_client import get_daily_bars

        return get_daily_bars(symbol, days=60)
