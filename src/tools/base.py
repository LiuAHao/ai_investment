#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
工具基类和工具规格定义
定义所有工具的统一接口
"""

from __future__ import annotations

import inspect
import time
import typing
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from agents.state import AssetType, ToolResult


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
        """获取工具规格（自动从 execute 签名推断 input_schema）"""
        return ToolSpec(
            name=self.name,
            description=self.description,
            input_schema=self._infer_input_schema(),
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

    # ---------- 工具参数 Schema 自动推断 ----------

    @staticmethod
    def _type_to_json(tp: Any) -> Dict[str, Any]:
        """将 Python 类型注解转为 JSON Schema 类型"""
        origin = getattr(tp, "__origin__", None)
        if origin is list or origin is List:
            args = getattr(tp, "__args__", (Any,))
            item = BaseTool._type_to_json(args[0]) if args else {"type": "string"}
            return {"type": "array", "items": item}
        if origin is dict or origin is Dict:
            return {"type": "object"}
        if tp is int or tp is float or origin is int or origin is float:
            return {"type": "integer"} if tp is int else {"type": "number"}
        if tp is bool:
            return {"type": "boolean"}
        return {"type": "string"}

    def coerce_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        根据 execute 签名将参数字符串数字强制转换为 int/float/bool。
        LLM function calling 传来的数字参数可能是字符串（如 "5"），统一转换。
        注意：模块级 `from __future__ import annotations` 会把注解变成字符串，
        需用 typing.get_type_hints 解析真实类型。
        """
        try:
            hints = typing.get_type_hints(self.execute)
        except Exception:
            hints = {}
        if not hints:
            return params
        coerced = dict(params)
        for name, value in coerced.items():
            if value is None or not isinstance(value, str):
                continue
            annotation = hints.get(name)
            if annotation is None:
                continue
            origin = getattr(annotation, "__origin__", annotation)
            try:
                if origin is int:
                    coerced[name] = int(value)
                elif origin is float:
                    coerced[name] = float(value)
                elif origin is bool:
                    coerced[name] = value.lower() in ("true", "1", "yes")
            except (TypeError, ValueError):
                pass  # 转换失败保留原值，交给工具自行处理
        return coerced

    def _infer_input_schema(self) -> Dict[str, Any]:
        """
        根据 execute 方法的签名自动生成 input_schema（JSON Schema）。
        排除 self / **kwargs / *args；有默认值的参数为非必填。
        注意：注解可能是字符串（`from __future__ import annotations`），
        用 typing.get_type_hints 解析真实类型。
        """
        try:
            hints = typing.get_type_hints(self.execute)
        except Exception:
            hints = {}
        try:
            sig = inspect.signature(self.execute)
            properties: Dict[str, Any] = {}
            required: List[str] = []
            for name, param in sig.parameters.items():
                if name in ("self", "kwargs", "args"):
                    continue
                if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                    continue
                annotation = hints.get(name, Any)
                type_schema = BaseTool._type_to_json(annotation)
                if param.default is not inspect.Parameter.empty:
                    type_schema["default"] = param.default
                properties[name] = type_schema
                if param.default is inspect.Parameter.empty:
                    required.append(name)
            return {
                "type": "object",
                "properties": properties,
                "required": required,
            }
        except (ValueError, TypeError):
            return {"type": "object", "properties": {}}

