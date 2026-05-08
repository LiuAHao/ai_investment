#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
分析工具
封装 V1 AnalysisAgent 的功能
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from agent.v2.state import AssetType
from tools.base import BaseTool, CostLevel, RiskLevel


class AnalysisTool(BaseTool):
    """综合分析工具"""

    name = "analysis"
    description = "综合多维度数据生成投资分析"
    timeout = 30

    asset_types = []  # 通用工具
    intents = ["asset_analysis", "comparison", "risk_check"]
    cost_level = CostLevel.HIGH
    risk_level = RiskLevel.LOW

    def execute(
        self,
        user_query: str,
        data_payload: Optional[Dict] = None,
        news_payload: Optional[Dict] = None,
        knowledge_payload: Optional[Dict] = None,
        preferences: Optional[Dict] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        from agent.analysis_agent import AnalysisAgent
        agent = AnalysisAgent()
        recommendation = agent.analyze(
            user_query=user_query,
            data_payload=data_payload or {},
            news_payload=news_payload or {},
            knowledge_payload=knowledge_payload or {},
            preferences=preferences,
        )
        return {"recommendation": recommendation}
