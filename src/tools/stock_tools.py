#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
股票数据工具
封装数据层 DataAgent 的功能，支持 A股 / 指数 / 场内ETF 的历史行情、技术指标与估值。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from agents.state import AssetType
from tools.base import BaseTool, CostLevel, RiskLevel


class StockDataTool(BaseTool):
    """A股/指数/ETF 历史数据和技术指标工具"""

    name = "cn_stock_history"
    description = "获取A股、A股指数(如沪深300/创业板指)或场内ETF的历史行情、技术指标与估值(PE/PB)"
    timeout = 20

    asset_types = [AssetType.CN_STOCK, AssetType.INDEX, AssetType.ETF]
    intents = ["asset_analysis", "risk_check", "comparison"]
    cost_level = CostLevel.MEDIUM
    freshness_requirement_seconds = 86400
    fallback_tools = ["cn_stock_spot_search"]
    risk_level = RiskLevel.LOW

    def execute(self, symbol: str, **kwargs) -> Dict[str, Any]:
        from data.stock_client import DataAgent

        agent = DataAgent()
        resolved = self._resolve_symbol(symbol)
        kind = self._infer_kind(query=symbol, code=resolved)
        summary = agent.analyze_daily_hist(symbol=resolved, kind=kind)
        technical = agent.analyze_technical_indicators(symbol=resolved, kind=kind)
        valuation = agent.fetch_valuation(symbol=resolved, kind=kind)
        return {
            "symbol": resolved,
            "query": symbol,
            "summary": summary,
            "technical": technical,
            "valuation": valuation,
        }

    @staticmethod
    def _resolve_symbol(symbol: str) -> str:
        """将资产名称/别名解析为 6 位代码；已是代码则原样返回"""
        if not symbol:
            return symbol
        value = str(symbol).strip()
        # 已经是 6 位数字代码
        if value.isdigit() and len(value) == 6:
            return value
        # 尝试资产主数据解析（名称/别名 → 代码）
        try:
            from asset import get_asset_master

            result = get_asset_master().search(value)
            if result:
                return result[0].symbol or value
        except Exception:
            pass
        return value

    @staticmethod
    def _infer_kind(query: str, code: str) -> Optional[str]:
        """通过资产主数据推断资产种类，供 tushare 分流（index/etf/fund/None=股票）"""
        try:
            from asset import get_asset_master
            from agents.state import AssetType

            master = get_asset_master()
            # 优先按原始查询文本匹配（区分"沪深300指数" vs "平安银行"）
            if query and not query.isdigit():
                results = master.search(query)
                for r in results:
                    if r.asset_type == AssetType.INDEX:
                        return "index"
                    if r.asset_type == AssetType.ETF:
                        return "etf"
            assets = master.find_by_symbol(code)
            types = {a.asset_type for a in assets}
            if types == {AssetType.INDEX}:
                return "index"
            if types == {AssetType.ETF}:
                return "etf"
            if types == {AssetType.FUND}:
                return "fund"
        except Exception:
            pass
        return None


class StockSpotTool(BaseTool):
    """A股/指数实时行情搜索工具"""

    name = "cn_stock_spot_search"
    description = "搜索A股或主要指数实时行情数据"
    timeout = 15

    asset_types = [AssetType.CN_STOCK, AssetType.INDEX]
    intents = ["asset_analysis", "market_overview"]
    cost_level = CostLevel.LOW
    freshness_requirement_seconds = 900
    risk_level = RiskLevel.LOW

    def execute(self, symbols: List[str], limit: int = 30, **kwargs) -> Dict[str, Any]:
        from data.stock_client import DataAgent

        agent = DataAgent()
        return agent.fetch_spot_em(symbols=symbols, limit=limit)
