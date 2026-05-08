#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
V2 LangGraph 编排核心测试
"""

import os
import sys

CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_SRC = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
if PROJECT_SRC not in sys.path:
    sys.path.insert(0, PROJECT_SRC)

from agent.v2.graph import build_graph, compile_graph, should_continue_execution
from agent.v2.state import InvestmentState, ToolResult


def test_graph_can_compile():
    """V2 图应可以成功构建并编译"""
    graph = build_graph()
    compiled = compile_graph()

    assert graph is not None
    assert compiled is not None


def test_should_replan_when_critical_tool_failed():
    """关键工具失败时应触发重新规划"""
    state = InvestmentState(
        session_id="s",
        user_id=1,
        query="分析宁德时代",
        tool_results=[
            ToolResult(
                tool_name="cn_stock_history",
                status="failed",
                error="行情源失败",
            )
        ],
    )

    assert should_continue_execution(state) == "replan"


def test_should_collect_after_replan_limit():
    """达到重规划次数上限后应进入证据收集，避免无限循环"""
    state = InvestmentState(
        session_id="s",
        user_id=1,
        query="分析宁德时代",
        replan_count=2,
        tool_results=[
            ToolResult(
                tool_name="cn_stock_history",
                status="failed",
                error="行情源失败",
            )
        ],
    )

    assert should_continue_execution(state) == "collect"
