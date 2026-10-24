#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
分析师注册表

新增分析师 = 加一个 spec + 一个验收用例，不改编排代码。
required_by 表示规则保底：满足对应 intent 时必须派发，LLM 不可删除。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AnalystSpec:
    key: str
    label: str
    evidence_categories: List[str] = field(default_factory=list)
    tool_names: List[str] = field(default_factory=list)
    required_by: List[str] = field(default_factory=list)
    max_iterations: int = 4
    description: str = ""


ANALYST_SPECS: Dict[str, AnalystSpec] = {
    "market": AnalystSpec(
        key="market",
        label="MarketAnalyst",
        evidence_categories=["market", "technical", "valuation"],
        tool_names=[
            "cn_stock_history",
            "us_stock_history",
            "fund_nav_history",
            "fund_profile",
            "etf_profile",
            "etf_tracking_index",
            "index_environment",
            "stock_fund_flow",
            "stock_valuation_band",
            "stock_events",
            "industry_context",
        ],
        required_by=["single_asset_research", "compare", "macro"],
        max_iterations=4,
        description="行情、技术形态、估值分位、指数环境",
    ),
    "news": AnalystSpec(
        key="news",
        label="NewsAnalyst",
        evidence_categories=["news", "announcement"],
        tool_names=["asset_news_search", "web_research", "stock_expectation", "stock_events"],
        required_by=["event"],
        max_iterations=3,
        description="事件、公告、舆情、时间线",
    ),
    "fundamental": AnalystSpec(
        key="fundamental",
        label="FundamentalAnalyst",
        evidence_categories=["fundamental"],
        tool_names=[
            "stock_financial_summary",
            "stock_financial_indicator",
            "stock_peer_compare",
            "fund_profile",
            "stock_expectation",
            "stock_valuation_band",
            "stock_events",
        ],
        required_by=["single_asset_research", "compare"],
        max_iterations=4,
        description="财务质量、成长、同业对比",
    ),
    "macro": AnalystSpec(
        key="macro",
        label="MacroAnalyst",
        evidence_categories=["macro", "policy"],
        tool_names=["macro_indicator", "index_environment", "asset_news_search"],
        required_by=["macro"],
        max_iterations=3,
        description="政策、利率、行业景气、宏观环境",
    ),
}

# 关键词触发（用于规则保底与 LLM 候选集）
_EVENT_KEYWORDS = ("财报", "业绩", "公告", "减持", "增持", "重组", "并购", "监管", "处罚",
                   "立案", "政策", "突发", "新闻", "舆情", "分红", "回购", "解禁")
_MACRO_KEYWORDS = ("宏观", "大盘", "市场环境", "指数", "利率", "政策", "PMI", "CPI", "GDP",
                   "汇率", "流动性", "经济", "行业景气")


def analyst_label(key: str) -> str:
    spec = ANALYST_SPECS.get(key)
    return spec.label if spec else key


def build_analyst(
    key: str,
    task_id: str = "",
    model: Optional[str] = None,
    ledger: Any = None,
    budget: Any = None,
    as_of: Optional[str] = None,
) -> Any:
    """按 key 构建分析师实例（惰性导入，避免循环依赖）"""
    spec = ANALYST_SPECS[key]
    if key == "market":
        from analysts.market import MarketAnalyst
        cls = MarketAnalyst
    elif key == "news":
        from analysts.news import NewsAnalyst
        cls = NewsAnalyst
    elif key == "fundamental":
        from analysts.fundamental import FundamentalAnalyst
        cls = FundamentalAnalyst
    elif key == "macro":
        from analysts.macro import MacroAnalyst
        cls = MacroAnalyst
    else:
        raise KeyError(f"未知分析师: {key}")

    agent = cls(task_id=task_id, model=model, ledger=ledger, budget=budget, as_of=as_of)
    agent.max_iterations = min(int(spec.max_iterations), int(agent.max_iterations) or spec.max_iterations)
    return agent


def rule_required(
    intent: str,
    query: str,
    has_assets: bool,
    asset_types: List[str] | None = None,
) -> List[str]:
    """
    规则保底：这些分析师必须派发，LLM 只能追加不能删除。
    ETF / 基金 / 指数不派个股财务分析师。
    """
    kinds = {str(k) for k in (asset_types or []) if k}
    has_stock = bool(kinds & {"cn_stock", "us_stock"})
    fund_like = bool(kinds & {"etf", "fund"})
    index_only = ("index" in kinds) and not has_stock and not fund_like

    required: List[str] = []
    if has_assets:
        required.append("market")
        if has_stock or not kinds:
            required.append("fundamental")
        if index_only:
            required.append("macro")
        else:
            required.append("news")
    if intent == "compare":
        for key in ("market", "news"):
            if key not in required:
                required.append(key)
        if (has_stock or not kinds) and "fundamental" not in required:
            required.append("fundamental")
    if intent == "sector":
        for key in ("market", "news", "macro"):
            if key not in required:
                required.append(key)
    if intent == "macro":
        for key in ("macro", "market"):
            if key not in required:
                required.append(key)
    if any(word in query for word in _EVENT_KEYWORDS) and "news" not in required:
        required.append("news")

    if not required:
        required = ["market", "macro"]
        if any(word in query for word in _EVENT_KEYWORDS):
            required.append("news")
    return required


def optional_candidates(required: List[str]) -> List[str]:
    """LLM 可追加的候选（排除已必选）"""
    return [key for key in ANALYST_SPECS if key not in required]


def tool_names_for(key: str) -> List[str]:
    spec = ANALYST_SPECS.get(key)
    return list(spec.tool_names) if spec else []


def evidence_categories_for(key: str) -> List[str]:
    spec = ANALYST_SPECS.get(key)
    return list(spec.evidence_categories) if spec else []
