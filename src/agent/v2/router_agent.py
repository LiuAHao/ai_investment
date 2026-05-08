#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
意图路由节点
判断用户问题的意图和需要的能力，支持追问识别
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from agent.v2.state import InvestmentState, IntentResult

logger = logging.getLogger(__name__)

FOLLOW_UP_KEYWORDS = [
    "那", "这个", "它", "这只", "上面", "刚才",
    "继续", "展开", "详细", "为什么", "依据",
]

FOLLOW_UP_PATTERNS = [
    r"如果.*呢",
    r"换成.*",
    r"和.*比",
    r"对比.*",
    r"长期.*短期",
    r"三个月",
    r"半年",
    r"一年",
    r"风险呢",
    r"还能买吗",
    r"值得.*吗",
]


def route_intent(state: InvestmentState) -> Dict[str, Any]:
    """
    意图路由
    
    职责：
    - 判断问题意图
    - 判断是否为追问
    - 判断需要哪些能力
    """
    logger.info("route_intent: 分析意图, query=%s", state.query[:50])

    query = state.query
    has_history = bool(state.chat_history) or bool(state.research_context)
    
    is_follow_up = _detect_follow_up(query, has_history, state)
    
    intent = _classify_intent(query, is_follow_up, state)

    trace = state.trace + [{
        "node": "route_intent",
        "status": "completed",
        "input_summary": f"query={state.query[:50]}, has_history={has_history}",
        "output_summary": f"intent={intent.primary_intent}, is_follow_up={is_follow_up}, confidence={intent.confidence}",
        "latency_ms": 0,
    }]

    return {
        "intent": intent,
        "trace": trace,
    }


def _detect_follow_up(query: str, has_history: bool, state: Optional[InvestmentState]) -> bool:
    """检测是否为追问"""
    if not has_history:
        return False

    for keyword in FOLLOW_UP_KEYWORDS:
        if keyword in query:
            return True

    for pattern in FOLLOW_UP_PATTERNS:
        if re.search(pattern, query):
            return True

    if state and state.research_context and state.research_context.current_assets:
        asset_keywords = []
        for asset in state.research_context.current_assets:
            if asset.name:
                asset_keywords.append(asset.name)
            if asset.symbol:
                asset_keywords.append(asset.symbol)
        
        has_asset_keyword = any(kw in query for kw in asset_keywords)
        if not has_asset_keyword and len(query) < 20:
            return True

    return False


def _classify_intent(query: str, is_follow_up: bool, state: InvestmentState) -> IntentResult:
    """分类意图"""
    query_lower = query.lower()

    if is_follow_up:
        follow_up_type = _classify_follow_up_type(query, state)
        return IntentResult(
            primary_intent="follow_up",
            secondary_intents=[follow_up_type] if follow_up_type else [],
            requires_realtime_data=follow_up_type in ("modify_horizon", "add_comparison"),
            requires_news=follow_up_type in ("modify_horizon", "news_impact"),
            requires_knowledge=follow_up_type == "ask_basis",
            confidence=0.8,
        )

    knowledge_keywords = ["什么是", "解释", "定义", "含义", "怎么理解", "介绍一下"]
    is_knowledge = any(kw in query for kw in knowledge_keywords)

    comparison_keywords = ["对比", "比较", "哪个好", "区别", "vs"]
    is_comparison = any(kw in query for kw in comparison_keywords)

    risk_keywords = ["风险", "止损", "仓位", "风控"]
    is_risk = any(kw in query for kw in risk_keywords)

    import re
    has_symbol = bool(re.search(r'\d{6}|[\u4e00-\u9fa5]{2,8}(?:股票|股份)', query))

    if is_knowledge:
        primary = "knowledge_query"
        requires_realtime = False
    elif is_comparison:
        primary = "comparison"
        requires_realtime = True
    else:
        primary = "asset_analysis"
        requires_realtime = True

    secondary = []
    if is_risk:
        secondary.append("risk_check")
    if is_comparison:
        secondary.append("comparison")

    confidence = 0.8
    if is_knowledge:
        confidence = 0.9

    return IntentResult(
        primary_intent=primary,
        secondary_intents=secondary,
        requires_realtime_data=requires_realtime,
        requires_news=requires_realtime,
        requires_macro=False,
        requires_knowledge=is_knowledge or requires_realtime,
        confidence=confidence,
    )


def _classify_follow_up_type(query: str, state: InvestmentState) -> Optional[str]:
    """分类追问类型"""
    horizon_keywords = ["三个月", "半年", "一年", "长期", "短期", "持有"]
    if any(kw in query for kw in horizon_keywords):
        return "modify_horizon"

    risk_keywords = ["保守", "激进", "稳健", "风险偏好"]
    if any(kw in query for kw in risk_keywords):
        return "modify_risk"

    basis_keywords = ["为什么", "依据", "原因", "理由", "怎么得出"]
    if any(kw in query for kw in basis_keywords):
        return "ask_basis"

    comparison_patterns = [r"和.*比", r"对比", r"换成", r"加上"]
    if any(re.search(pattern, query) for pattern in comparison_patterns):
        return "add_comparison"

    news_keywords = ["利空", "利好", "新闻", "消息", "影响"]
    if any(kw in query for kw in news_keywords):
        return "news_impact"

    return None


def _extract_horizon_from_query(query: str) -> Optional[str]:
    """从查询中提取投资周期"""
    if "三个月" in query or "3个月" in query:
        return "short"
    elif "半年" in query or "6个月" in query:
        return "medium"
    elif "一年" in query or "1年" in query:
        return "long"
    elif "长期" in query:
        return "long"
    elif "短期" in query:
        return "short"
    return None
