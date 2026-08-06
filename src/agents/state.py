#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
多 Agent 状态模型
定义 Agent 任务、结果、资产、证据、工具结果等统一数据结构。
由旧 agent/v2/state.py 迁移而来，tools 层与 asset 层均依赖此模块。
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
    scenarios: List[Dict[str, Any]] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    # P2 结构化风险模型：[{type, desc, probability, impact, priced_in}]
    # type: 行业/财务/政策/市场/技术/流动性；probability: high/medium/low；impact: high/medium/low
    structured_risks: List[Dict[str, Any]] = Field(default_factory=list)
    action_options: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    data_limitations: List[str] = Field(default_factory=list)
    reasoning: str = ""  # 分析推理过程（多空因素权衡）
    bull_cases: List[Dict[str, Any]] = Field(default_factory=list)  # 看多论据 [{论据, 强度, 来源}]
    bear_cases: List[Dict[str, Any]] = Field(default_factory=list)  # 看空论据 [{论据, 强度, 来源}]
    information_gaps: List[str] = Field(default_factory=list)  # 信息缺口/待验证
    time_frame: str = ""  # 结论有效期（短期/中期/长期）
    compliance_disclaimer: str = "以上内容仅为投资研究辅助，不构成确定性收益承诺或直接交易指令。"
    created_at: datetime = Field(default_factory=datetime.now)


class AgentTask(BaseModel):
    """编排器派发给子 Agent 的任务"""
    agent_name: str
    goal: str
    assets: List[Asset] = Field(default_factory=list)
    context: str = ""
    risk_preference: str = ""


class AgentResult(BaseModel):
    """Agent 执行结果"""
    agent_name: str
    conclusion: str = ""
    evidence_refs: List[str] = Field(default_factory=list)
    tool_calls: List[ToolResult] = Field(default_factory=list)
    thinking_log: List[str] = Field(default_factory=list)
    error: Optional[str] = None
    degraded: bool = False


class ResearchContext(BaseModel):
    """
    研究上下文
    支持连续追问和记忆（进程内内存态）
    """
    session_id: str
    current_assets: List[Asset] = Field(default_factory=list)
    last_intent: Optional[IntentResult] = None
    last_answer: Optional[str] = None
    last_evidence_ids: List[str] = Field(default_factory=list)
    user_preferences: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
