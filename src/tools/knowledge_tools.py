#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
知识库查询工具
封装 V1 KnowledgeAgent 的功能
"""

from __future__ import annotations

from typing import Any, Dict

from agents.state import AssetType
from tools.base import BaseTool, CostLevel, RiskLevel


class KnowledgeQueryTool(BaseTool):
    """知识库查询工具"""

    name = "investment_framework_search"
    description = "从知识库检索投资框架、合规规则、指标口径与分析方法"
    timeout = 15

    asset_types = []  # 通用工具，不限资产类型
    intents = ["knowledge_query", "asset_analysis", "risk_check"]
    cost_level = CostLevel.LOW
    risk_level = RiskLevel.LOW

    def execute(self, query: str, top_k: int = 5, **kwargs) -> Dict[str, Any]:
        from rag.knowledge_tool import query_investment_knowledge
        return query_investment_knowledge(query=query, top_k=top_k)
