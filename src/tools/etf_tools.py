#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ETF工具
提供ETF净值、跟踪指数等数据
数据源优先级：tushare（fund_basic）> akshare 东方财富
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from agents.state import AssetType
from tools.base import BaseTool, CostLevel, RiskLevel

logger = logging.getLogger(__name__)


class EtfProfileTool(BaseTool):
    """ETF基本信息工具"""

    name = "etf_profile"
    description = "获取ETF基本信息、规模、成交额"
    timeout = 15

    asset_types = [AssetType.ETF]
    intents = ["asset_analysis", "comparison"]
    cost_level = CostLevel.LOW
    risk_level = RiskLevel.LOW

    def execute(self, symbol: str, **kwargs) -> Dict[str, Any]:
        """获取ETF基本信息（tushare fund_basic 优先，失败回退 akshare）"""
        try:
            from data.tushare_client import get_fund_profile

            profile = get_fund_profile(symbol)
            if profile:
                return {"symbol": symbol, "profile": profile}
        except Exception as e:
            logger.warning("tushare etf_profile 失败 %s, 回退 akshare: %s", symbol, e)

        try:
            import akshare as ak

            df = ak.fund_etf_spot_em()
            if df is not None and not df.empty:
                row = df[df["代码"] == symbol]
                if not row.empty:
                    data = row.iloc[0].to_dict()
                    return {"symbol": symbol, "profile": data}
        except Exception as e:
            logger.warning("akshare etf_profile 失败 %s: %s", symbol, e)

        return {"symbol": symbol, "profile": {}, "note": "ETF数据暂不可用"}


class EtfTrackingTool(BaseTool):
    """ETF跟踪指数工具"""

    name = "etf_tracking_index"
    description = "获取ETF跟踪指数信息"
    timeout = 15

    asset_types = [AssetType.ETF]
    intents = ["asset_analysis"]
    cost_level = CostLevel.LOW
    risk_level = RiskLevel.LOW

    def execute(self, symbol: str, **kwargs) -> Dict[str, Any]:
        """获取ETF跟踪指数"""
        try:
            from asset import get_asset_master

            master = get_asset_master()
            assets = master.find_by_symbol(symbol)
            if assets:
                asset = assets[0]
                tracking_index = asset.metadata.get("tracking_index")
                if tracking_index:
                    index_assets = master.find_by_symbol(tracking_index)
                    if index_assets:
                        return {
                            "symbol": symbol,
                            "tracking_index": tracking_index,
                            "index_name": index_assets[0].name,
                        }
        except Exception as e:
            logger.warning("etf_tracking_index 失败 %s: %s", symbol, e)
        return {"symbol": symbol, "tracking_index": None, "note": "跟踪指数数据暂不可用"}
