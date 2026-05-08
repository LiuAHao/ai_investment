#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
V2 Schema 定义
定义 API 请求/响应和内部数据结构
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from agent.v2.state import AssetType


class QueryRequest(BaseModel):
    """V2 查询请求"""
    query: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = None
    preferences: Dict[str, Any] = Field(default_factory=dict)


class QueryResponse(BaseModel):
    """V2 查询响应"""
    task_id: str
    session_id: str
    status: str = "processing"
    message: str = "查询已提交"


class TaskStatusResponse(BaseModel):
    """任务状态响应"""
    task_id: str
    session_id: str
    status: str
    progress: int = 0
    current_node: Optional[str] = None
    trace: List[Dict[str, Any]] = Field(default_factory=list)
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class AgentTrace(BaseModel):
    """Agent 执行轨迹"""
    node: str
    status: str
    input_summary: Optional[str] = None
    output_summary: Optional[str] = None
    latency_ms: int = 0
    created_at: str


class ToolCallRecord(BaseModel):
    """工具调用记录"""
    tool_name: str
    params: Dict[str, Any] = Field(default_factory=dict)
    result_status: str
    result_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    latency_ms: int = 0


class AssetInfo(BaseModel):
    """资产信息响应"""
    asset_id: str
    asset_type: AssetType
    symbol: Optional[str] = None
    name: Optional[str] = None
    market: Optional[str] = None
    exchange: Optional[str] = None
    confidence: float = 1.0


class AssetResolveResponse(BaseModel):
    """资产解析响应"""
    selected_assets: List[AssetInfo] = Field(default_factory=list)
    candidates: List[AssetInfo] = Field(default_factory=list)
    ambiguous: bool = False
    need_user_clarification: bool = False
    reason: str = ""


class V2WorkflowResult(BaseModel):
    """V2 工作流结果"""
    session_id: str
    query: str
    final_answer: Optional[str] = None
    assets: List[AssetInfo] = Field(default_factory=list)
    evidence_count: int = 0
    tool_calls: List[ToolCallRecord] = Field(default_factory=list)
    trace: List[AgentTrace] = Field(default_factory=list)
    degraded: bool = False
    errors: List[str] = Field(default_factory=list)
    created_at: str
    completed_at: Optional[str] = None


INTENT_TYPES = {
    "asset_analysis": "资产分析",
    "knowledge_query": "知识问答",
    "risk_check": "风险检查",
    "comparison": "对比分析",
    "market_overview": "市场概览",
    "follow_up": "追问",
}

ASSET_TYPE_LABELS = {
    AssetType.CN_STOCK: "A股",
    AssetType.HK_STOCK: "港股",
    AssetType.US_STOCK: "美股",
    AssetType.FUND: "基金",
    AssetType.ETF: "ETF",
    AssetType.INDEX: "指数",
    AssetType.MACRO: "宏观指标",
    AssetType.INDUSTRY: "行业",
    AssetType.UNKNOWN: "未知",
}
