#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
主控 Agent：协调新闻与股票 Agent
支持 LLM 任务拆解与工具调用链路
"""

from typing import Dict, Optional

from agent.news_agent import NewsAgent
from agent.openai_decision_agent import OpenAIDecisionAgent
from agent.stock_agent import StockAgent


class MasterAgent:
    """主控 Agent"""

    def __init__(
        self,
        news_agent: Optional[NewsAgent] = None,
        stock_agent: Optional[StockAgent] = None,
        decision_agent: Optional[OpenAIDecisionAgent] = None,
    ):
        self.news_agent = news_agent or NewsAgent()
        self.stock_agent = stock_agent or StockAgent()
        self.decision_agent = decision_agent or OpenAIDecisionAgent()

    def run(self, symbol: str, news_limit: int = 20) -> Dict:
        """
        执行最小化工作流：股票数据 + 新闻标题

        Args:
            symbol: 股票代码
            news_limit: 新闻标题数量

        Returns:
            结果字典
        """
        stock_summary = self.stock_agent.fetch_daily_hist(symbol=symbol)
        titles = self.news_agent.fetch_titles(limit=news_limit)
        return {
            "symbol": symbol,
            "stock_summary": stock_summary,
            "news_titles": titles,
        }

    def run_query(self, user_query: str) -> str:
        """
        执行 LLM 决策链路：问题 -> 任务拆解 -> 工具调用 -> 结论与风险

        Args:
            user_query: 用户问题

        Returns:
            LLM 输出文本
        """
        return self.decision_agent.run(user_query)
