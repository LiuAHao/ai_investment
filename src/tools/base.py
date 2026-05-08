#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
工具基类和工具规格定义
定义所有工具的统一接口
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from agent.v2.state import AssetType, ToolResult


class CostLevel(str, Enum):
    """成本级别"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskLevel(str, Enum):
    """风险级别"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ToolSpec(BaseModel):
    """
    工具规格定义
    描述工具的元数据、能力、约束
    """
    name: str
    description: str
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    output_schema: Dict[str, Any] = Field(default_factory=dict)
    asset_types: List[AssetType] = Field(default_factory=list)
    intents: List[str] = Field(default_factory=list)
    cost_level: CostLevel = CostLevel.LOW
    timeout_seconds: int = 20
    freshness_requirement_seconds: Optional[int] = None
    fallback_tools: List[str] = Field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.LOW


class RegisteredTool:
    """已注册的工具"""

    def __init__(self, spec: ToolSpec, handler: "BaseTool"):
        self.spec = spec
        self.handler = handler

    @property
    def name(self) -> str:
        return self.spec.name

    def execute(self, **kwargs) -> ToolResult:
        """执行工具"""
        return self.handler.run(**kwargs)

    def run(self, **kwargs) -> ToolResult:
        """兼容执行器的统一调用入口"""
        return self.execute(**kwargs)


class BaseTool(ABC):
    """工具基类"""

    name: str = ""
    description: str = ""
    timeout: int = 20

    asset_types: List[AssetType] = []
    intents: List[str] = []
    cost_level: CostLevel = CostLevel.LOW
    freshness_requirement_seconds: Optional[int] = None
    fallback_tools: List[str] = []
    risk_level: RiskLevel = RiskLevel.LOW

    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        """执行工具，返回结果字典"""
        pass

    def run(self, **kwargs) -> ToolResult:
        """运行工具并返回标准化结果"""
        t0 = time.time()
        try:
            data = self.execute(**kwargs)
            return ToolResult(
                tool_name=self.name,
                status="success",
                data=data,
                source=self.description,
                fetched_at=datetime.now(),
                confidence=1.0,
                latency_ms=int((time.time() - t0) * 1000),
            )
        except Exception as e:
            return ToolResult(
                tool_name=self.name,
                status="failed",
                data={},
                error=str(e),
                fetched_at=datetime.now(),
                confidence=0.0,
                latency_ms=int((time.time() - t0) * 1000),
            )

    def get_spec(self) -> ToolSpec:
        """获取工具规格"""
        return ToolSpec(
            name=self.name,
            description=self.description,
            asset_types=self.asset_types,
            intents=self.intents,
            cost_level=self.cost_level,
            timeout_seconds=self.timeout,
            freshness_requirement_seconds=self.freshness_requirement_seconds,
            fallback_tools=self.fallback_tools,
            risk_level=self.risk_level,
        )

    def to_schema(self) -> Dict[str, Any]:
        """导出工具 Schema"""
        spec = self.get_spec()
        return spec.model_dump()
