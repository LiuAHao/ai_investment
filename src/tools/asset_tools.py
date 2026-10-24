#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
资产解析工具
供编排 Agent 使用：从用户查询中识别资产（代码/名称/别名）。
封装 asset/resolver.py 的规则逻辑。
"""

from __future__ import annotations

from typing import Any, Dict, List

from agents.state import AssetResolveInput, AssetResolveResult, AssetType
from tools.base import BaseTool, CostLevel, RiskLevel


class AssetResolveTool(BaseTool):
    """资产解析工具"""

    name = "asset_resolve"
    description = "从用户查询中识别投资资产（A股/美股/ETF/基金等），返回代码、名称与类型"
    timeout = 10

    asset_types = []
    intents = []
    cost_level = CostLevel.LOW
    risk_level = RiskLevel.LOW

    def execute(self, query: str, **kwargs) -> Dict[str, Any]:
        """执行资产解析"""
        from asset.resolver import resolve_assets

        intent = None
        try:
            from agents.state import IntentResult
            intent_data = kwargs.get("intent")
            if intent_data and isinstance(intent_data, dict):
                intent = IntentResult(**intent_data)
        except Exception:
            intent = None

        input_data = AssetResolveInput(
            query=query,
            chat_history=kwargs.get("chat_history") or [],
            previous_assets=kwargs.get("previous_assets") or [],
            intent=intent,
        )
        result = resolve_assets(input_data)

        return {
            "summary": self._format_result(result),
            "selected_assets": [a.model_dump() for a in result.selected_assets],
            "candidates": [a.model_dump() for a in result.candidates],
            "ambiguous": result.ambiguous,
            "need_user_clarification": result.need_user_clarification,
            "reason": result.reason,
        }

    @staticmethod
    def _format_result(result: AssetResolveResult) -> str:
        if result.selected_assets:
            names = [f"{a.name or a.symbol}({a.asset_type.value})" for a in result.selected_assets]
            return f"识别到 {len(names)} 个资产: {', '.join(names)}"
        if result.need_user_clarification and result.candidates:
            names = [f"{a.name or a.symbol}({a.asset_type.value})" for a in result.candidates]
            return f"存在多个候选资产，需要澄清: {', '.join(names)}"
        return "未识别到具体资产"
