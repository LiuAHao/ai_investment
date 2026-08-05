#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
工具注册中心
管理所有可用工具的注册、发现和选择
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from agents.state import AssetType, ToolResult
from tools.base import BaseTool, RegisteredTool, ToolSpec

logger = logging.getLogger(__name__)


class ToolRegistry:
    """工具注册中心"""

    def __init__(self):
        self._tools: Dict[str, RegisteredTool] = {}

    def register(self, tool: BaseTool) -> None:
        """注册工具"""
        if not tool.name:
            raise ValueError("工具必须有名称")
        spec = tool.get_spec()
        self._tools[tool.name] = RegisteredTool(spec=spec, handler=tool)
        logger.info("注册工具: %s, asset_types=%s, intents=%s", 
                    tool.name, [t.value for t in tool.asset_types], tool.intents)

    def get(self, name: str) -> Optional[RegisteredTool]:
        """获取工具"""
        return self._tools.get(name)

    def list_tools(self) -> List[str]:
        """列出所有工具名称"""
        return list(self._tools.keys())

    def get_all_specs(self) -> List[ToolSpec]:
        """获取所有工具规格"""
        return [tool.spec for tool in self._tools.values()]

    def get_all_schemas(self) -> List[Dict[str, Any]]:
        """获取所有工具 Schema"""
        return [tool.spec.model_dump() for tool in self._tools.values()]

    def find_tools(
        self,
        asset_type: Optional[AssetType] = None,
        intent: Optional[str] = None,
        requires_realtime: bool = False,
        requires_news: bool = False,
    ) -> List[RegisteredTool]:
        """
        根据条件查找工具
        
        Args:
            asset_type: 资产类型
            intent: 意图
            requires_realtime: 是否需要实时数据
            requires_news: 是否需要新闻
            
        Returns:
            匹配的工具列表
        """
        results = []

        for tool in self._tools.values():
            if asset_type and tool.spec.asset_types and asset_type not in tool.spec.asset_types:
                continue
            if intent and tool.spec.intents and intent not in tool.spec.intents:
                continue

            score = 0.0

            if asset_type and asset_type in tool.spec.asset_types:
                score += 1.0
            elif not tool.spec.asset_types:
                score += 0.5

            if intent and intent in tool.spec.intents:
                score += 1.0
            elif not tool.spec.intents:
                score += 0.5

            if requires_realtime and tool.spec.freshness_requirement_seconds:
                if tool.spec.freshness_requirement_seconds <= 900:
                    score += 0.5

            if requires_news and "news" in tool.spec.name:
                score += 0.5

            if score > 0:
                results.append((score, tool))

        results.sort(key=lambda x: x[0], reverse=True)
        return [tool for _, tool in results]

    def execute(self, name: str, params: Dict[str, Any]) -> ToolResult:
        """执行指定工具（自动类型转换 LLM 字符串参数）"""
        tool = self.get(name)
        if not tool:
            raise ValueError(f"工具 {name} 未注册")
        coerced = tool.handler.coerce_params(params or {})
        return tool.execute(**coerced)


_global_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """获取全局工具注册中心"""
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
        _register_default_tools(_global_registry)
    return _global_registry


def _register_default_tools(registry: ToolRegistry) -> None:
    """注册默认工具"""
    from tools.asset_tools import AssetResolveTool
    from tools.stock_tools import StockDataTool, StockSpotTool
    from tools.news_tools import NewsSearchTool
    from tools.knowledge_tools import KnowledgeQueryTool
    from tools.fund_tools import FundNavTool, FundProfileTool
    from tools.etf_tools import EtfProfileTool, EtfTrackingTool
    from tools.us_stock_tools import UsStockQuoteTool, UsStockHistoryTool

    registry.register(AssetResolveTool())
    registry.register(StockDataTool())
    registry.register(StockSpotTool())
    registry.register(NewsSearchTool())
    registry.register(KnowledgeQueryTool())

    registry.register(FundProfileTool())
    registry.register(FundNavTool())
    registry.register(EtfProfileTool())
    registry.register(EtfTrackingTool())
    registry.register(UsStockQuoteTool())
    registry.register(UsStockHistoryTool())
