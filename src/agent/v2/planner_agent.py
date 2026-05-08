#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
任务规划节点
根据意图和资产生成执行计划，使用工具注册中心选择工具
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from agent.v2.state import (
    Asset,
    AssetType,
    ExecutionPlan,
    ExecutionStep,
    IntentResult,
    InvestmentState,
)

logger = logging.getLogger(__name__)


def plan_tasks(state: InvestmentState) -> Dict[str, Any]:
    """
    任务规划
    
    职责：
    - 根据意图和资产生成执行计划
    - 从工具注册中心选择工具
    - 设置停止条件和超时
    """
    logger.info("plan_tasks: 生成执行计划")

    intent = state.intent
    assets = state.assets
    steps: List[ExecutionStep] = []

    if _is_high_risk_query(state.query):
        plan = ExecutionPlan(steps=[], max_iterations=1, total_timeout=5)
        trace = state.trace + [{
            "node": "plan_tasks",
            "status": "blocked",
            "input_summary": "high_risk_query_detected",
            "output_summary": "planned 0 steps for compliance review",
            "latency_ms": 0,
        }]
        return {
            "plan": plan,
            "trace": trace,
        }

    if intent is None:
        steps.append(ExecutionStep(
            step_id="default_analysis",
            tool_name="analysis",
            params={"user_query": state.query},
        ))
    else:
        if intent.primary_intent == "knowledge_query":
            steps.append(ExecutionStep(
                step_id="knowledge",
                tool_name="investment_framework_search",
                params={"query": state.query, "top_k": 5},
            ))
        else:
            asset_steps = _plan_asset_steps(assets, intent)
            steps.extend(asset_steps)

            if intent.requires_news:
                keywords = _build_keywords(state.query, assets)
                steps.append(ExecutionStep(
                    step_id="news",
                    tool_name="asset_news_search",
                    params={"keywords": keywords, "limit": 5},
                ))

            if intent.requires_knowledge:
                steps.append(ExecutionStep(
                    step_id="knowledge",
                    tool_name="investment_framework_search",
                    params={"query": state.query, "top_k": 5},
                ))

            analysis_deps = [s.step_id for s in steps]
            steps.append(ExecutionStep(
                step_id="analysis",
                tool_name="analysis",
                params={"user_query": state.query},
                depends_on=analysis_deps,
            ))

    plan = ExecutionPlan(steps=steps, max_iterations=6, total_timeout=120)
    next_replan_count = state.replan_count
    if any(r.status == "failed" and r.tool_name in ("cn_stock_history", "analysis") for r in state.tool_results):
        next_replan_count += 1

    trace = state.trace + [{
        "node": "plan_tasks",
        "status": "completed",
        "input_summary": f"intent={intent.primary_intent if intent else 'none'}, assets={len(assets)}",
        "output_summary": f"planned {len(steps)} steps: {[s.tool_name for s in steps]}",
        "latency_ms": 0,
    }]

    return {
        "plan": plan,
        "replan_count": next_replan_count,
        "trace": trace,
    }


def _plan_asset_steps(assets: List[Asset], intent: IntentResult) -> List[ExecutionStep]:
    """根据资产类型规划工具步骤"""
    steps = []
    from tools.registry import get_tool_registry
    registry = get_tool_registry()

    for i, asset in enumerate(assets):
        asset_type = asset.asset_type

        if asset_type == AssetType.CN_STOCK and registry.get("cn_stock_history"):
            steps.append(ExecutionStep(
                step_id=f"cn_stock_history_{i}",
                tool_name="cn_stock_history",
                params={"symbol": asset.symbol},
            ))
        elif asset_type == AssetType.US_STOCK:
            if not registry.get("us_stock_quote") or not registry.get("us_stock_history"):
                continue
            steps.append(ExecutionStep(
                step_id=f"us_stock_quote_{i}",
                tool_name="us_stock_quote",
                params={"symbol": asset.symbol},
            ))
            steps.append(ExecutionStep(
                step_id=f"us_stock_history_{i}",
                tool_name="us_stock_history",
                params={"symbol": asset.symbol},
            ))
        elif asset_type == AssetType.ETF:
            if not registry.get("etf_profile"):
                continue
            steps.append(ExecutionStep(
                step_id=f"etf_profile_{i}",
                tool_name="etf_profile",
                params={"symbol": asset.symbol},
            ))
            if registry.get("etf_tracking_index"):
                steps.append(ExecutionStep(
                    step_id=f"etf_tracking_{i}",
                    tool_name="etf_tracking_index",
                    params={"symbol": asset.symbol},
                ))
        elif asset_type == AssetType.FUND:
            if not registry.get("fund_profile"):
                continue
            steps.append(ExecutionStep(
                step_id=f"fund_profile_{i}",
                tool_name="fund_profile",
                params={"fund_code": asset.symbol},
            ))
            if registry.get("fund_nav_history"):
                steps.append(ExecutionStep(
                    step_id=f"fund_nav_{i}",
                    tool_name="fund_nav_history",
                    params={"fund_code": asset.symbol},
                ))

    return steps


def _build_keywords(query: str, assets: list) -> List[str]:
    """构建搜索关键词"""
    import re
    keywords = []
    for asset in assets:
        if asset.name:
            keywords.append(asset.name)
        elif asset.symbol:
            keywords.append(asset.symbol)
    cleaned = re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9 ]", " ", query)
    parts = [p.strip() for p in cleaned.split() if len(p.strip()) >= 2]
    keywords.extend(parts[:3])
    return keywords[:5] if keywords else ["投资"]


def _is_high_risk_query(query: str) -> bool:
    """识别应直接进入合规链路的高风险请求"""
    if not query:
        return False

    patterns = [
        r"必涨",
        r"稳赚",
        r"保证.*收益",
        r"稳赚.*不赔",
        r"满仓.*买",
        r"闭眼.*买",
        r"无风险.*收益",
        r"内部.*消息",
        r"内幕.*消息",
        r"忽略.*所有.*规则",
        r"忽略.*系统",
    ]
    return any(re.search(pattern, query) for pattern in patterns)


def _get_tools_for_asset_type(asset_type: AssetType) -> List[str]:
    """获取资产类型对应的工具列表"""
    from tools.registry import get_tool_registry
    registry = get_tool_registry()
    tools = registry.find_tools(asset_type=asset_type)
    return [t.name for t in tools]
