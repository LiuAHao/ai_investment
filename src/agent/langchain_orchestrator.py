#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LangChain 编排器（可选）
优先通过 AgentExecutor 调用子 Agent 工具，失败时由上层回退到自研编排。
"""

from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from agent.agent_protocol import AgentResult, WorkflowResult
from agent.llm_common import get_env


class LangChainOrchestrator:
    """基于 LangChain AgentExecutor 的主控编排器"""

    def __init__(self, stock_agent, news_agent, analysis_agent, knowledge_fn):
        self.stock_agent = stock_agent
        self.news_agent = news_agent
        self.analysis_agent = analysis_agent
        self.knowledge_fn = knowledge_fn

    @staticmethod
    def _extract_symbol(text: str) -> Optional[str]:
        if not text:
            return None
        pattern = r"\b(?:[A-Za-z]{2})?\d{6}(?:\.(?:SZ|SS|SH|BJ))?\b"
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            return None
        token = match.group(0).upper()
        if token.startswith(("SH", "SZ", "BJ")):
            token = token[2:]
        if "." in token:
            token = token.split(".")[0]
        return token

    @staticmethod
    def _extract_keywords(text: str, symbol: Optional[str]) -> List[str]:
        base = [symbol] if symbol else []
        cleaned = re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9 ]", " ", text or "")
        parts = [p.strip() for p in cleaned.split() if len(p.strip()) >= 2]
        return [item for item in (base + parts[:4]) if item]

    @staticmethod
    def _safe_json_loads(payload: str) -> Dict[str, Any]:
        try:
            value = json.loads(payload)
            if isinstance(value, dict):
                return value
            return {"value": value}
        except Exception:
            return {"raw": payload}

    @staticmethod
    def is_available() -> bool:
        try:
            import langchain  # noqa: F401
            import langchain_openai  # noqa: F401

            return True
        except Exception:
            return False

    def _build_executor(self):
        from langchain.agents import AgentExecutor, create_tool_calling_agent
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.tools import tool
        from langchain_openai import ChatOpenAI

        @tool
        def data_agent_tool(symbol: str) -> str:
            """调用数据Agent获取行情与技术指标，入参为股票代码。"""
            summary = self.stock_agent.analyze_daily_hist(symbol=symbol)
            technical = self.stock_agent.analyze_technical_indicators(symbol=symbol)
            return json.dumps(
                {
                    "symbol": symbol,
                    "summary": summary,
                    "technical": technical,
                },
                ensure_ascii=False,
                default=str,
            )

        @tool
        def news_agent_tool(keywords: str) -> str:
            """调用新闻Agent获取关键词相关新闻，入参为以空格分隔的关键词。"""
            keyword_list = [part.strip() for part in str(keywords).split() if part.strip()]
            result = self.news_agent.get_relevant_titles(
                keywords=keyword_list,
                limit=5,
                web_limit=5,
            )
            return json.dumps(result, ensure_ascii=False, default=str)

        @tool
        def knowledge_agent_tool(query: str) -> str:
            """调用知识库Agent执行RAG检索，入参为查询问题。"""
            result = self.knowledge_fn(query=query, top_k=5)
            return json.dumps(result, ensure_ascii=False, default=str)

        model = get_env("OPENAI_MODEL") or get_env("DEEPSEEK_MODEL") or "deepseek-chat"
        api_key = get_env("DEEPSEEK_API_KEY") or get_env("OPENAI_API_KEY")
        base_url = get_env("DEEPSEEK_BASE_URL") or get_env("OPENAI_BASE_URL") or None

        llm_kwargs: Dict[str, Any] = {
            "model": model,
            "temperature": 0,
            "api_key": api_key,
        }
        if base_url:
            llm_kwargs["base_url"] = base_url

        llm = ChatOpenAI(**llm_kwargs)
        tools = [data_agent_tool, news_agent_tool, knowledge_agent_tool]

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是投资分析系统的主控Agent。"
                    "请优先识别股票代码并调用数据工具；"
                    "对新闻敏感问题调用新闻工具；"
                    "对方法论/估值/风险框架问题调用知识工具。"
                    "可多次调用工具，但不要编造工具结果。"
                    "最后用JSON输出，字段包含: summary, used_tools, symbol。",
                ),
                ("human", "{input}"),
                ("placeholder", "{agent_scratchpad}"),
            ]
        )

        agent = create_tool_calling_agent(llm=llm, tools=tools, prompt=prompt)
        executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=False,
            return_intermediate_steps=True,
            max_iterations=6,
            handle_parsing_errors=True,
        )
        return executor

    def execute(self, user_query: str, preferences: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """执行 LangChain 编排并返回统一结构"""
        symbol = self._extract_symbol(user_query)
        keywords = self._extract_keywords(user_query, symbol)
        task_plan = {
            "query": user_query,
            "symbol": symbol,
            "tasks": [
                {"agent": "data_agent", "task": "get_stock_summary", "params": {"symbol": symbol}},
                {"agent": "news_agent", "task": "get_relevant_news", "params": {"keywords": keywords, "limit": 5}},
                {"agent": "knowledge_agent", "task": "query_knowledge", "params": {"query": user_query, "top_k": 5}},
                {"agent": "analysis_agent", "task": "synthesize", "params": {}},
            ],
            "orchestrator": "langchain",
        }

        executor = self._build_executor()
        start = time.time()
        response = executor.invoke({"input": user_query})
        _ = int((time.time() - start) * 1000)

        intermediate_steps = response.get("intermediate_steps", []) or []

        data_payload: Dict[str, Any] = {}
        news_payload: Dict[str, Any] = {}
        knowledge_payload: Dict[str, Any] = {}
        agent_results: List[AgentResult] = []

        called = {
            "data_agent_tool": False,
            "news_agent_tool": False,
            "knowledge_agent_tool": False,
        }

        for action, observation in intermediate_steps:
            tool_name = getattr(action, "tool", "")
            obs_data = self._safe_json_loads(str(observation))
            if tool_name == "data_agent_tool":
                called["data_agent_tool"] = True
                data_payload = obs_data
                agent_results.append(AgentResult(agent="DataAgent", status="completed", data=obs_data, latency_ms=0))
            elif tool_name == "news_agent_tool":
                called["news_agent_tool"] = True
                news_payload = obs_data
                agent_results.append(AgentResult(agent="NewsAgent", status="completed", data=obs_data, latency_ms=0))
            elif tool_name == "knowledge_agent_tool":
                called["knowledge_agent_tool"] = True
                knowledge_payload = obs_data
                agent_results.append(AgentResult(agent="KnowledgeAgent", status="completed", data=obs_data, latency_ms=0))

        if not called["data_agent_tool"]:
            if symbol:
                try:
                    summary = self.stock_agent.analyze_daily_hist(symbol=symbol)
                    technical = self.stock_agent.analyze_technical_indicators(symbol=symbol)
                    data_payload = {"symbol": symbol, "summary": summary, "technical": technical}
                    agent_results.append(AgentResult(agent="DataAgent", status="completed", data=data_payload, latency_ms=0))
                except Exception as exc:
                    agent_results.append(AgentResult(agent="DataAgent", status="failed", data={}, error=str(exc), latency_ms=0))
            else:
                agent_results.append(
                    AgentResult(
                        agent="DataAgent",
                        status="skipped",
                        data={"reason": "未识别到股票代码"},
                        error="未识别到股票代码",
                        latency_ms=0,
                    )
                )

        if not called["news_agent_tool"]:
            try:
                news_payload = self.news_agent.get_relevant_titles(keywords=keywords, limit=5, web_limit=5)
                agent_results.append(AgentResult(agent="NewsAgent", status="completed", data=news_payload, latency_ms=0))
            except Exception as exc:
                agent_results.append(AgentResult(agent="NewsAgent", status="failed", data={}, error=str(exc), latency_ms=0))

        if not called["knowledge_agent_tool"]:
            try:
                knowledge_payload = self.knowledge_fn(query=user_query, top_k=5)
                agent_results.append(AgentResult(agent="KnowledgeAgent", status="completed", data=knowledge_payload, latency_ms=0))
            except Exception as exc:
                agent_results.append(AgentResult(agent="KnowledgeAgent", status="failed", data={}, error=str(exc), latency_ms=0))

        try:
            recommendation = self.analysis_agent.analyze(
                user_query=user_query,
                data_payload=data_payload,
                news_payload=news_payload,
                knowledge_payload=knowledge_payload,
                preferences=preferences,
            )
            agent_results.append(
                AgentResult(
                    agent="AnalysisAgent",
                    status="completed",
                    data={"recommendation": recommendation},
                    latency_ms=0,
                )
            )
        except Exception as exc:
            recommendation = "分析阶段失败：系统未能完成综合推理，请稍后重试。"
            agent_results.append(
                AgentResult(
                    agent="AnalysisAgent",
                    status="failed",
                    data={},
                    error=str(exc),
                    latency_ms=0,
                )
            )

        degraded = any(item.status == "failed" for item in agent_results)
        workflow = WorkflowResult(
            query=user_query,
            symbol=symbol,
            degraded=degraded,
            task_plan=task_plan,
            agent_results=agent_results,
            recommendation=recommendation,
        )
        return workflow.to_dict()
