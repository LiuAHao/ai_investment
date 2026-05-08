#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
V2 状态模型
定义 LangGraph 图的状态结构
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class AssetType(str, Enum):
    """资产类型枚举"""
    CN_STOCK = "cn_stock"
    HK_STOCK = "hk_stock"
    US_STOCK = "us_stock"
    FUND = "fund"
    ETF = "etf"
    INDEX = "index"
    MACRO = "macro"
    INDUSTRY = "industry"
    UNKNOWN = "unknown"


class EvidenceType(str, Enum):
    """证据类型枚举"""
    MARKET_DATA = "market_data"
    FINANCIAL_DATA = "financial_data"
    TECHNICAL_INDICATOR = "technical_indicator"
    FUNDAMENTAL = "fundamental"
    NEWS = "news"
    MACRO = "macro"
    RAG_KNOWLEDGE = "rag_knowledge"
    USER_PROFILE = "user_profile"
    PORTFOLIO = "portfolio"


class Polarity(str, Enum):
    """情感极性"""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"


class Asset(BaseModel):
    """
    统一资产模型
    支持 A股、港股、美股、基金、ETF、指数、宏观、行业
    """
    asset_id: str = ""
    asset_type: AssetType = AssetType.UNKNOWN
    symbol: Optional[str] = None
    name: Optional[str] = None
    market: Optional[str] = None
    currency: Optional[str] = None
    exchange: Optional[str] = None
    confidence: float = 1.0
    aliases: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        """初始化后自动生成 asset_id"""
        if not self.asset_id and self.symbol and self.asset_type:
            self.asset_id = f"{self.asset_type.value}:{self.symbol}"


class AssetResolveInput(BaseModel):
    """资产解析输入"""
    query: str
    chat_history: List[Dict[str, str]] = Field(default_factory=list)
    previous_assets: List[Asset] = Field(default_factory=list)
    intent: Optional[IntentResult] = None


class AssetResolveResult(BaseModel):
    """资产解析结果"""
    selected_assets: List[Asset] = Field(default_factory=list)
    candidates: List[Asset] = Field(default_factory=list)
    ambiguous: bool = False
    need_user_clarification: bool = False
    reason: str = ""


class IntentResult(BaseModel):
    """意图识别结果"""
    primary_intent: str
    secondary_intents: List[str] = Field(default_factory=list)
    user_horizon: Optional[str] = None
    requires_realtime_data: bool = False
    requires_news: bool = False
    requires_macro: bool = False
    requires_knowledge: bool = False
    confidence: float = 0.0


class ExecutionStep(BaseModel):
    """执行计划步骤"""
    step_id: str
    tool_name: str
    params: Dict[str, Any] = Field(default_factory=dict)
    depends_on: List[str] = Field(default_factory=list)
    timeout: int = 20


class ExecutionPlan(BaseModel):
    """执行计划"""
    steps: List[ExecutionStep] = Field(default_factory=list)
    max_iterations: int = 6
    total_timeout: int = 120


class ToolResult(BaseModel):
    """
    工具执行结果
    支持数据新鲜度、来源追踪、置信度
    """
    tool_name: str
    status: Literal["success", "failed", "skipped", "partial"] = "success"
    asset_id: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)
    source: Optional[str] = None
    source_url: Optional[str] = None
    data_timestamp: Optional[datetime] = None
    fetched_at: datetime = Field(default_factory=datetime.now)
    freshness_seconds: Optional[int] = None
    confidence: float = 1.0
    error: Optional[str] = None
    latency_ms: int = 0
    step_id: Optional[str] = None


class EvidenceItem(BaseModel):
    """
    证据项
    支持来源追溯、置信度、重要性、情感极性
    """
    evidence_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    evidence_type: EvidenceType = EvidenceType.MARKET_DATA
    asset_id: Optional[str] = None
    title: str = ""
    summary: str = ""
    raw: Dict[str, Any] = Field(default_factory=dict)
    source: str = ""
    source_url: Optional[str] = None
    observed_at: Optional[datetime] = None
    confidence: float = 1.0
    importance: float = 0.5
    polarity: Optional[Polarity] = None
    limitations: List[str] = Field(default_factory=list)
    relevance_score: float = 0.0


class InvestmentAnswer(BaseModel):
    """
    结构化投资答案
    """
    answer_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    query: str = ""
    assets: List[Asset] = Field(default_factory=list)
    summary: str = ""
    key_points: List[str] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)
    scenarios: Dict[str, str] = Field(default_factory=dict)
    risks: List[str] = Field(default_factory=list)
    action_options: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    data_limitations: List[str] = Field(default_factory=list)
    compliance_disclaimer: str = "以上内容仅为投资研究辅助，不构成确定性收益承诺或直接交易指令。"
    created_at: datetime = Field(default_factory=datetime.now)


class ResearchContext(BaseModel):
    """
    研究上下文
    支持连续追问和记忆
    """
    session_id: str
    user_id: int
    current_assets: List[Asset] = Field(default_factory=list)
    last_intent: Optional[IntentResult] = None
    last_answer: Optional[str] = None
    last_evidence_ids: List[str] = Field(default_factory=list)
    key_assumptions: List[Dict[str, Any]] = Field(default_factory=list)
    user_preferences: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class TraceEntry(BaseModel):
    """执行轨迹记录"""
    node: str
    status: str
    input_summary: Optional[str] = None
    output_summary: Optional[str] = None
    latency_ms: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class InvestmentState(BaseModel):
    """
    V2 核心状态模型
    LangGraph 图在节点间传递的状态
    """
    session_id: str
    user_id: int
    query: str
    chat_history: List[Dict[str, str]] = Field(default_factory=list)
    user_profile: Dict[str, Any] = Field(default_factory=dict)
    intent: Optional[IntentResult] = None
    assets: List[Asset] = Field(default_factory=list)
    asset_candidates: List[Asset] = Field(default_factory=list)
    ambiguous_assets: bool = False
    plan: Optional[ExecutionPlan] = None
    tool_results: List[ToolResult] = Field(default_factory=list)
    evidence_items: List[EvidenceItem] = Field(default_factory=list)
    draft_answer: Optional[str] = None
    final_answer: Optional[str] = None
    investment_answer: Optional[InvestmentAnswer] = None
    research_context: Optional[ResearchContext] = None
    degraded: bool = False
    errors: List[str] = Field(default_factory=list)
    trace: List[Dict[str, Any]] = Field(default_factory=list)
    replan_count: int = 0
    critic_score: Optional[float] = None
    critic_issues: List[str] = Field(default_factory=list)
    compliance_passed: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    model_config = ConfigDict(arbitrary_types_allowed=True)
