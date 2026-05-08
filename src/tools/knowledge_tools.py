#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
知识库查询工具
封装 V1 KnowledgeAgent 的功能
"""

from __future__ import annotations

from typing import Any, Dict

from agent.v2.state import AssetType
from tools.base import BaseTool, CostLevel, RiskLevel


class KnowledgeQueryTool(BaseTool):
    """知识库查询工具"""

    name = "investment_framework_search"
    description = "从知识库检索投资框架和知识"
    timeout = 15

    asset_types = []  # 通用工具，不限资产类型
    intents = ["knowledge_query", "asset_analysis", "risk_check"]
    cost_level = CostLevel.LOW
    risk_level = RiskLevel.LOW

    def execute(self, query: str, top_k: int = 5, **kwargs) -> Dict[str, Any]:
        from agent.knowledge_agent import KnowledgeAgent
        agent = KnowledgeAgent()
        return agent.query(query=query, top_k=top_k)
