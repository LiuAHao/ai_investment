#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
主控 Agent：协调数据/新闻/分析 Agent
支持 Phase 2 的多 Agent 编排链路
"""

import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, Optional, List

from agent.analysis_agent import AnalysisAgent
from agent.agent_protocol import AgentResult, WorkflowResult
from agent.data_agent import DataAgent
from agent.knowledge_agent import KnowledgeAgent
from agent.langchain_orchestrator import LangChainOrchestrator
from agent.llm_common import AgentConfig
from agent.news_agent import NewsAgent
from agent.symbol_resolver import SymbolResolver


class MasterAgent:
    """主控 Agent"""

    def __init__(
        self,
        news_agent: Optional[NewsAgent] = None,
        stock_agent: Optional[DataAgent] = None,
        analysis_agent: Optional[AnalysisAgent] = None,
        knowledge_agent: Optional[KnowledgeAgent] = None,
    ):
        self.news_agent = news_agent or NewsAgent()
        self.stock_agent = stock_agent or DataAgent()
        self.analysis_agent = analysis_agent or AnalysisAgent()
        self.knowledge_agent = knowledge_agent or KnowledgeAgent()
        self.symbol_resolver = SymbolResolver()
        self.config = AgentConfig()

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
    def _extract_name_candidates(text: str) -> List[str]:
        stopwords = {
            "分析",
            "财报",
            "走势",
            "后期",
            "影响",
            "今天",
            "今日",
            "复盘",
            "资金",
            "流向",
            "建议",
            "风险",
            "提示",
            "一下",
            "请问",
            "请",
            "关于",
            "以及",
        }
        terms = re.findall(r"[\u4e00-\u9fa5]{2,8}", text or "")
        candidates: List[str] = []
        for term in terms:
            if term in stopwords:
                continue
            if any(word in term for word in stopwords):
                stripped = term
                for sw in stopwords:
                    stripped = stripped.replace(sw, "")
                if len(stripped) >= 2:
                    term = stripped
                else:
                    continue
            if term not in candidates:
                candidates.append(term)
        return candidates[:5]

    def _resolve_symbol(self, user_query: str) -> Optional[str]:
        resolved = self.symbol_resolver.resolve(user_query)
        symbol = resolved.get("symbol")
        if symbol:
            return symbol

        candidates = self._extract_name_candidates(user_query)
        for name in candidates:
            try:
                spot = self.stock_agent.fetch_spot_em(symbols=[name], limit=30)
                items = spot.get("data", []) if isinstance(spot, dict) else []
                if not items:
                    continue

                exact_code = None
                fuzzy_code = None
                for item in items:
                    item_name = str(item.get("名称") or item.get("name") or "").strip()
                    item_code = str(item.get("代码") or item.get("code") or "").strip()
                    if not item_code:
                        continue
                    if item_name == name:
                        exact_code = item_code
                        break
                    if name in item_name and not fuzzy_code:
                        fuzzy_code = item_code

                found = exact_code or fuzzy_code
                if found:
                    return found
            except Exception:
                continue

        return None

    @staticmethod
    def _extract_keywords(text: str, symbol: Optional[str]) -> List[str]:
        base = [symbol] if symbol else []
        cleaned = re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9 ]", " ", text or "")
        parts = [p.strip() for p in cleaned.split() if len(p.strip()) >= 2]
        return [item for item in (base + parts[:4]) if item]

    def build_task_plan(self, user_query: str) -> Dict[str, Any]:
        """生成统一任务计划（JSON Schema 语义）"""
        symbol = self._resolve_symbol(user_query)
        keywords = self._extract_keywords(user_query, symbol)
        tasks = []
        if symbol:
            tasks.append({"agent": "data_agent", "task": "get_stock_summary", "params": {"symbol": symbol}})
        else:
            tasks.append({"agent": "data_agent", "task": "skip", "params": {"reason": "未识别到股票代码"}})
        tasks.append({"agent": "news_agent", "task": "get_relevant_news", "params": {"keywords": keywords, "limit": 5}})
        tasks.append({"agent": "knowledge_agent", "task": "query_knowledge", "params": {"query": user_query, "top_k": 5}})
        tasks.append({"agent": "analysis_agent", "task": "synthesize", "params": {}})
        return {
            "query": user_query,
            "symbol": symbol,
            "tasks": tasks,
        }

    # ------------------------------------------------------------------
    #  数据收集 Agent 执行：单个 Agent 执行逻辑
    # ------------------------------------------------------------------

    def _run_data_agent(self, symbol: Optional[str]) -> tuple:
        """执行 DataAgent，返回 (data_payload, AgentResult)"""
        if not symbol:
            return {}, AgentResult(
                agent="DataAgent",
                status="skipped",
                data={"reason": "未识别到股票代码"},
                error="未识别到股票代码",
                latency_ms=0,
            )
        t0 = time.time()
        try:
            summary = self.stock_agent.analyze_daily_hist(symbol=symbol)
            technical = self.stock_agent.analyze_technical_indicators(symbol=symbol)
            data_payload = {"symbol": symbol, "summary": summary, "technical": technical}
            return data_payload, AgentResult(
                agent="DataAgent",
                status="completed",
                data=data_payload,
                latency_ms=int((time.time() - t0) * 1000),
            )
        except Exception as exc:
            return {}, AgentResult(
                agent="DataAgent",
                status="failed",
                data={},
                error=str(exc),
                latency_ms=int((time.time() - t0) * 1000),
            )

    def _run_news_agent(self, keywords: List[str]) -> tuple:
        """执行 NewsAgent，返回 (news_payload, AgentResult)"""
        t0 = time.time()
        try:
            news_payload = self.news_agent.get_relevant_titles(keywords=keywords, limit=5, web_limit=5)
            return news_payload, AgentResult(
                agent="NewsAgent",
                status="completed",
                data=news_payload,
                latency_ms=int((time.time() - t0) * 1000),
            )
        except Exception as exc:
            return {}, AgentResult(
                agent="NewsAgent",
                status="failed",
                data={},
                error=str(exc),
                latency_ms=int((time.time() - t0) * 1000),
            )

    def _run_knowledge_agent(self, user_query: str) -> tuple:
        """执行 KnowledgeAgent，返回 (knowledge_payload, AgentResult)"""
        t0 = time.time()
        try:
            knowledge_payload = self.knowledge_agent.query(query=user_query, top_k=5)
            return knowledge_payload, AgentResult(
                agent="KnowledgeAgent",
                status="completed",
                data=knowledge_payload,
                latency_ms=int((time.time() - t0) * 1000),
            )
        except Exception as exc:
            return {}, AgentResult(
                agent="KnowledgeAgent",
                status="failed",
                data={},
                error=str(exc),
                latency_ms=int((time.time() - t0) * 1000),
            )

    # ------------------------------------------------------------------
    #  串行执行三个数据收集 Agent
    # ------------------------------------------------------------------

    def _execute_collectors_serial(
        self,
        symbol: Optional[str],
        user_query: str,
        keywords: List[str],
        on_agent_complete: Optional[callable] = None,
    ) -> tuple:
        """串行执行 DataAgent → NewsAgent → KnowledgeAgent"""
        agent_results: List[AgentResult] = []

        data_payload, stock_result = self._run_data_agent(symbol)
        agent_results.append(stock_result)
        if on_agent_complete:
            on_agent_complete("DataAgent", stock_result.to_dict())

        news_payload, news_result = self._run_news_agent(keywords)
        agent_results.append(news_result)
        if on_agent_complete:
            on_agent_complete("NewsAgent", news_result.to_dict())

        knowledge_payload, knowledge_result = self._run_knowledge_agent(user_query)
        agent_results.append(knowledge_result)
        if on_agent_complete:
            on_agent_complete("KnowledgeAgent", knowledge_result.to_dict())

        return data_payload, news_payload, knowledge_payload, agent_results

    # ------------------------------------------------------------------
    #  并行执行三个数据收集 Agent（ThreadPoolExecutor）
    # ------------------------------------------------------------------

    def _execute_collectors_parallel(
        self,
        symbol: Optional[str],
        user_query: str,
        keywords: List[str],
        on_agent_complete: Optional[callable] = None,
    ) -> tuple:
        """并行执行 DataAgent / NewsAgent / KnowledgeAgent"""
        data_payload: Dict[str, Any] = {}
        news_payload: Dict[str, Any] = {}
        knowledge_payload: Dict[str, Any] = {}
        results_map: Dict[str, AgentResult] = {}
        timeout = self.config.parallel_timeout

        with ThreadPoolExecutor(max_workers=3, thread_name_prefix="agent") as pool:
            futures = {
                pool.submit(self._run_data_agent, symbol): "DataAgent",
                pool.submit(self._run_news_agent, keywords): "NewsAgent",
                pool.submit(self._run_knowledge_agent, user_query): "KnowledgeAgent",
            }
            for future in as_completed(futures, timeout=timeout):
                agent_name = futures[future]
                try:
                    payload, result = future.result()
                except Exception as exc:
                    payload = {}
                    result = AgentResult(
                        agent=agent_name, status="failed", data={}, error=str(exc)
                    )

                results_map[agent_name] = result
                if agent_name == "DataAgent":
                    data_payload = payload
                elif agent_name == "NewsAgent":
                    news_payload = payload
                else:
                    knowledge_payload = payload

                if on_agent_complete:
                    on_agent_complete(agent_name, result.to_dict())

        # 结果按固定顺序排列，保证输出一致
        agent_results: List[AgentResult] = []
        for name in ("DataAgent", "NewsAgent", "KnowledgeAgent"):
            if name in results_map:
                agent_results.append(results_map[name])
            else:
                agent_results.append(AgentResult(
                    agent=name, status="failed", data={}, error="执行超时"
                ))

        return data_payload, news_payload, knowledge_payload, agent_results

    # ------------------------------------------------------------------
    #  Phase 2 主编排入口
    # ------------------------------------------------------------------

    def execute_phase2(self, user_query: str, preferences: Optional[Dict[str, Any]] = None, on_agent_complete: Optional[callable] = None) -> Dict[str, Any]:
        """
        执行 Phase 2 多 Agent 编排
        
        Args:
            user_query: 用户查询
            preferences: 用户偏好
            on_agent_complete: Agent完成时的回调函数，参数为 (agent_name, agent_result)
        """
        mode = self.config.orchestrator_mode
        if mode in {"langchain", "auto"}:
            try:
                if LangChainOrchestrator.is_available():
                    orchestrator = LangChainOrchestrator(
                        stock_agent=self.stock_agent,
                        news_agent=self.news_agent,
                        analysis_agent=self.analysis_agent,
                        knowledge_fn=self.knowledge_agent.query,
                    )
                    langchain_result = orchestrator.execute(
                        user_query=user_query,
                        preferences=preferences,
                    )
                    plan = langchain_result.get("task_plan", {})
                    plan["orchestrator"] = "langchain"
                    langchain_result["task_plan"] = plan
                    return langchain_result
            except Exception as exc:
                if mode == "langchain":
                    fallback_mode = "custom"
                else:
                    fallback_mode = "custom"
                mode = fallback_mode
                fallback_error = str(exc)
            else:
                fallback_error = ""
        else:
            fallback_error = ""

        task_plan = self.build_task_plan(user_query)
        task_plan["orchestrator"] = "custom"
        task_plan["parallel"] = self.config.parallel_enabled
        if fallback_error:
            task_plan["fallback_reason"] = fallback_error
        symbol = task_plan.get("symbol")
        keywords = self._extract_keywords(user_query, symbol)

        if self.config.parallel_enabled:
            data_payload, news_payload, knowledge_payload, agent_results = \
                self._execute_collectors_parallel(symbol, user_query, keywords, on_agent_complete)
        else:
            data_payload, news_payload, knowledge_payload, agent_results = \
                self._execute_collectors_serial(symbol, user_query, keywords, on_agent_complete)

        # AnalysisAgent 执行
        t3 = time.time()
        try:
            recommendation = self.analysis_agent.analyze(
                user_query=user_query,
                data_payload=data_payload,
                news_payload=news_payload,
                knowledge_payload=knowledge_payload,
                preferences=preferences,
            )
            analysis_result = AgentResult(
                agent="AnalysisAgent",
                status="completed",
                data={"recommendation": recommendation},
                latency_ms=int((time.time() - t3) * 1000),
            )
        except Exception as exc:
            recommendation = "分析阶段失败：系统未能完成综合推理，请稍后重试。"
            analysis_result = AgentResult(
                agent="AnalysisAgent",
                status="failed",
                data={},
                error=str(exc),
                latency_ms=int((time.time() - t3) * 1000),
            )
        agent_results.append(analysis_result)
        if on_agent_complete:
            on_agent_complete("AnalysisAgent", analysis_result.to_dict())

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

    def run(self, symbol: str, news_limit: int = 20) -> Dict:
        """
        执行最小化工作流：股票数据 + 新闻标题

        Args:
            symbol: 股票代码
            news_limit: 新闻标题数量

        Returns:
            结果字典
        """
        query = f"分析股票 {symbol}"
        result = self.execute_phase2(query)
        return {
            "symbol": symbol,
            "stock_summary": result.get("agent_results", [{}])[0].get("data", {}).get("summary", {}),
            "news_titles": result.get("agent_results", [{}]),
        }

    def run_query(self, user_query: str, preferences: Optional[Dict] = None) -> str:
        """
        执行 LLM 决策链路：问题 -> 任务拆解 -> 工具调用 -> 结论与风险

        Args:
            user_query: 用户问题

        Returns:
            LLM 输出文本
        """
        result = self.execute_phase2(user_query=user_query, preferences=preferences)
        return result.get("recommendation", "")
