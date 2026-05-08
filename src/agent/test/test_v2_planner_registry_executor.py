#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
V2 规划、工具注册和执行器测试
"""

import os
import sys

CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_SRC = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
if PROJECT_SRC not in sys.path:
    sys.path.insert(0, PROJECT_SRC)

from agent.v2.executor import execute_tools
from agent.v2.planner_agent import plan_tasks
from agent.v2.state import (
    Asset,
    AssetType,
    ExecutionPlan,
    ExecutionStep,
    IntentResult,
    InvestmentState,
    ToolResult,
)
from tools.registry import get_tool_registry


def test_registry_filters_tools_by_asset_type_and_intent():
    """工具注册中心应按资产类型和意图过滤工具"""
    registry = get_tool_registry()

    etf_tools = [tool.name for tool in registry.find_tools(asset_type=AssetType.ETF, intent="asset_analysis")]
    cn_tools = [tool.name for tool in registry.find_tools(asset_type=AssetType.CN_STOCK, intent="asset_analysis")]

    assert "etf_profile" in etf_tools
    assert "etf_tracking_index" in etf_tools
    assert "cn_stock_history" not in etf_tools
    assert "cn_stock_history" in cn_tools
    assert "fund_profile" not in cn_tools


def test_planner_knowledge_query_only_uses_rag_tool():
    """知识问答不应强制规划行情和新闻工具"""
    state = InvestmentState(
        session_id="s1",
        user_id=1,
        query="什么是市盈率",
        intent=IntentResult(
            primary_intent="knowledge_query",
            requires_knowledge=True,
        ),
    )

    result = plan_tasks(state)
    tool_names = [step.tool_name for step in result["plan"].steps]

    assert tool_names == ["investment_framework_search"]


def test_planner_selects_etf_tools_for_etf_asset():
    """ETF 资产应规划 ETF 工具，而不是 A 股历史行情工具"""
    state = InvestmentState(
        session_id="s2",
        user_id=1,
        query="沪深300ETF 怎么看",
        intent=IntentResult(
            primary_intent="asset_analysis",
            requires_news=True,
            requires_knowledge=True,
        ),
        assets=[
            Asset(
                asset_id="etf:510300",
                asset_type=AssetType.ETF,
                symbol="510300",
                name="华泰柏瑞沪深300ETF",
            )
        ],
    )

    result = plan_tasks(state)
    tool_names = [step.tool_name for step in result["plan"].steps]

    assert "etf_profile" in tool_names
    assert "etf_tracking_index" in tool_names
    assert "asset_news_search" in tool_names
    assert "investment_framework_search" in tool_names
    assert "analysis" in tool_names
    assert "cn_stock_history" not in tool_names


def test_executor_passes_successful_tool_payloads_to_analysis(monkeypatch):
    """执行器应把成功工具结果映射给 analysis 工具"""
    captured = {}

    class FakeTool:
        def __init__(self, name):
            self.name = name

        def run(self, **kwargs):
            if self.name == "cn_stock_history":
                return ToolResult(
                    tool_name=self.name,
                    status="success",
                    data={"summary": {"symbol": "300750"}, "technical": {"trend": "震荡"}},
                )
            if self.name == "asset_news_search":
                return ToolResult(
                    tool_name=self.name,
                    status="success",
                    data={"relevant_titles": ["新闻A"]},
                )
            if self.name == "investment_framework_search":
                return ToolResult(
                    tool_name=self.name,
                    status="success",
                    data={"results": [{"text": "风险框架"}]},
                )
            captured.update(kwargs)
            return ToolResult(
                tool_name=self.name,
                status="success",
                data={"recommendation": "综合分析完成"},
            )

    class FakeRegistry:
        def get(self, name):
            return FakeTool(name)

    monkeypatch.setattr("tools.registry.get_tool_registry", lambda: FakeRegistry())

    state = InvestmentState(
        session_id="s3",
        user_id=1,
        query="分析宁德时代",
        plan=ExecutionPlan(
            steps=[
                ExecutionStep(step_id="data", tool_name="cn_stock_history", params={"symbol": "300750"}),
                ExecutionStep(step_id="news", tool_name="asset_news_search", params={"keywords": ["宁德时代"]}),
                ExecutionStep(step_id="knowledge", tool_name="investment_framework_search", params={"query": "分析宁德时代"}),
                ExecutionStep(step_id="analysis", tool_name="analysis", params={"user_query": "分析宁德时代"}),
            ]
        ),
        user_profile={"risk_preference": "稳健型"},
    )

    result = execute_tools(state)
    tool_results = result["tool_results"]

    assert [item.tool_name for item in tool_results][-1] == "analysis"
    assert tool_results[-1].status == "success"
    assert captured["data_payload"]["summary"]["symbol"] == "300750"
    assert captured["news_payload"]["relevant_titles"] == ["新闻A"]
    assert captured["knowledge_payload"]["results"][0]["text"] == "风险框架"
    assert captured["preferences"]["risk_preference"] == "稳健型"
