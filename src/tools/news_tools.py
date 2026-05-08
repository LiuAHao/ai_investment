#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
新闻搜索工具
封装 V1 NewsAgent 的功能
"""

from __future__ import annotations

from typing import Any, Dict, List

from agent.v2.state import AssetType
from tools.base import BaseTool, CostLevel, RiskLevel


class NewsSearchTool(BaseTool):
    """新闻搜索工具"""

    name = "asset_news_search"
    description = "搜索资产相关新闻资讯"
    timeout = 20

    asset_types = [
        AssetType.CN_STOCK, AssetType.HK_STOCK, AssetType.US_STOCK,
        AssetType.ETF, AssetType.FUND, AssetType.INDUSTRY,
    ]
    intents = ["asset_analysis", "risk_check", "market_overview"]
    cost_level = CostLevel.MEDIUM
    freshness_requirement_seconds = 86400
    risk_level = RiskLevel.LOW

    def execute(self, keywords: List[str], limit: int = 5, **kwargs) -> Dict[str, Any]:
        from agent.news_agent import NewsAgent
        agent = NewsAgent()
        return agent.get_relevant_titles(keywords=keywords, limit=limit, web_limit=limit)
