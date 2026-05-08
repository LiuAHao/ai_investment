#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
工具执行节点
按计划调用工具并收集结果
"""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Any, Dict, List

from agent.v2.state import InvestmentState, ToolResult

logger = logging.getLogger(__name__)

TOOL_TIMEOUT = int(os.getenv("AGENT_V2_TOOL_TIMEOUT", "20"))


def execute_tools(state: InvestmentState) -> Dict[str, Any]:
    """
    执行工具
    
    职责：
    - 按 plan 调用工具
    - 支持并行执行无依赖工具
    - 收集 ToolResult
    - 捕获异常并降级
    """
    logger.info("execute_tools: 执行工具计划")

    if not state.plan or not state.plan.steps:
        trace = state.trace + [{
            "node": "execute_tools",
            "status": "skipped",
            "input_summary": "no plan steps",
            "output_summary": "skipped",
            "latency_ms": 0,
        }]
        return {"tool_results": [], "trace": trace}

    from tools.registry import get_tool_registry
    registry = get_tool_registry()

    results: List[ToolResult] = []
    dependent_steps = []
    independent_steps = []

    for step in state.plan.steps:
        if step.tool_name == "analysis":
            dependent_steps.append(step)
        else:
            independent_steps.append(step)

    if independent_steps:
        with ThreadPoolExecutor(max_workers=4, thread_name_prefix="v2_tool") as pool:
            futures = {}
            for step in independent_steps:
                future = pool.submit(_execute_single_tool, registry, step.tool_name, step.params)
                futures[future] = step

            for future, step in futures.items():
                step = futures[future]
                try:
                    result = future.result(timeout=step.timeout or TOOL_TIMEOUT)
                    result.step_id = step.step_id
                    _attach_asset_id(result, step.params, state)
                    results.append(result)
                except TimeoutError:
                    failed = ToolResult(
                        tool_name=step.tool_name,
                        status="failed",
                        error=f"工具执行超时: {step.timeout or TOOL_TIMEOUT}s",
                        step_id=step.step_id,
                    )
                    _attach_asset_id(failed, step.params, state)
                    results.append(failed)
                except Exception as e:
                    failed = ToolResult(
                        tool_name=step.tool_name,
                        status="failed",
                        error=str(e),
                        step_id=step.step_id,
                    )
                    _attach_asset_id(failed, step.params, state)
                    results.append(failed)

    for step in dependent_steps:
        data_payload = {}
        news_payload = {}
        knowledge_payload = {}

        for r in results:
            if r.status in ("success", "partial"):
                if r.tool_name in ("cn_stock_history", "us_stock_quote", "us_stock_history", "etf_profile", "etf_tracking_index", "fund_profile", "fund_nav_history"):
                    data_payload = r.data
                elif r.tool_name == "asset_news_search":
                    news_payload = r.data
                elif r.tool_name == "investment_framework_search":
                    knowledge_payload = r.data

        params = {
            "user_query": state.query,
            "data_payload": data_payload,
            "news_payload": news_payload,
            "knowledge_payload": knowledge_payload,
            "preferences": state.user_profile,
        }
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix="v2_tool") as pool:
            future = pool.submit(_execute_single_tool, registry, step.tool_name, params)
            try:
                result = future.result(timeout=step.timeout or TOOL_TIMEOUT)
                result.step_id = step.step_id
                _attach_asset_id(result, step.params, state)
                results.append(result)
            except TimeoutError:
                failed = ToolResult(
                    tool_name=step.tool_name,
                    status="failed",
                    error=f"工具执行超时: {step.timeout or TOOL_TIMEOUT}s",
                    step_id=step.step_id,
                )
                _attach_asset_id(failed, step.params, state)
                results.append(failed)

    success_count = sum(1 for r in results if r.status in ("success", "partial"))
    trace = state.trace + [{
        "node": "execute_tools",
        "status": "completed",
        "input_summary": f"plan has {len(state.plan.steps)} steps",
        "output_summary": f"executed {len(results)} tools, {success_count} succeeded",
        "latency_ms": 0,
    }]

    return {
        "tool_results": results,
        "trace": trace,
    }


def _execute_single_tool(registry, tool_name: str, params: Dict[str, Any]) -> ToolResult:
    """执行单个工具"""
    tool = registry.get(tool_name)
    if not tool:
        return ToolResult(
            tool_name=tool_name,
            status="failed",
            error=f"工具 {tool_name} 未注册",
        )
    return tool.run(**params)


def _attach_asset_id(result: ToolResult, params: Dict[str, Any], state: InvestmentState) -> None:
    """根据工具参数和当前资产列表补充 asset_id"""
    if result.asset_id:
        return

    symbol = params.get("symbol") or params.get("fund_code")
    if not symbol:
        return

    for asset in state.assets:
        if asset.symbol and str(asset.symbol).upper() == str(symbol).upper():
            result.asset_id = asset.asset_id
            return
