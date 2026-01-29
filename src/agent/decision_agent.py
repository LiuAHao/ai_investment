#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
基于 OpenAI 接口的最小化智能决策 Agent
"""

import json
import os
import re
from typing import Any, Dict, List, Optional

from openai import OpenAI

from agent.news_agent import NewsAgent
from agent.stock_agent import StockAgent

import logging

logger = logging.getLogger(__name__)


def _get_env(name: str, default: str = "") -> str:
    value = os.getenv(name)
    return value if value is not None else default


def _load_env_file() -> None:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    env_path = os.path.join(project_root, ".env")
    if not os.path.isfile(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception:
        pass


def _build_client() -> OpenAI:
    _load_env_file()
    api_key = _get_env("DEEPSEEK_API_KEY") or _get_env("OPENAI_API_KEY")
    base_url = _get_env("DEEPSEEK_BASE_URL") or _get_env("OPENAI_BASE_URL")
    if base_url:
        return OpenAI(api_key=api_key, base_url=base_url)
    return OpenAI(api_key=api_key)


class DecisionAgent:
    """最小化主控 Agent（OpenAI Function Calling）"""

    def __init__(self, model: Optional[str] = None):
        self.client = _build_client()
        self.model = model or _get_env("OPENAI_MODEL") or _get_env("DEEPSEEK_MODEL") or "deepseek-chat"
        self.news_agent = NewsAgent()
        self.stock_agent = StockAgent()
        self._tool_cache: Dict[str, Any] = {}

    def _tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_stock_analysis",
                    "description": "获取股票历史行情分析摘要",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {"type": "string"},
                            "start_date": {"type": "string"},
                            "end_date": {"type": "string"},
                            "period": {"type": "string"},
                            "adjust": {"type": "string"}
                        },
                        "required": ["symbol"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_stock_history",
                    "description": "获取股票历史行情摘要（非技术分析）",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {"type": "string"},
                            "start_date": {"type": "string"},
                            "end_date": {"type": "string"},
                            "period": {"type": "string"},
                            "adjust": {"type": "string"}
                        },
                        "required": ["symbol"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_stock_summary",
                    "description": "汇总股票基础信息与技术指标",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {"type": "string"}
                        },
                        "required": ["symbol"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_stock_tech",
                    "description": "获取股票技术指标摘要",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {"type": "string"},
                            "start_date": {"type": "string"},
                            "end_date": {"type": "string"},
                            "period": {"type": "string"},
                            "adjust": {"type": "string"}
                        },
                        "required": ["symbol"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_sse_summary",
                    "description": "获取上交所市场总貌（收盘后统计）",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_szse_summary",
                    "description": "获取深交所市场总貌（收盘后统计）",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "date": {"type": "string"}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_sse_deal_daily",
                    "description": "获取上交所每日概况（收盘后统计）",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "date": {"type": "string"}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_relevant_titles",
                    "description": "按关键词筛选相关新闻标题",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "keywords": {"type": "array", "items": {"type": "string"}},
                            "limit": {"type": "integer"}
                        },
                        "required": ["keywords"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "联网搜索最新信息",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "limit": {"type": "integer"}
                        },
                        "required": ["query"]
                    }
                }
            },
        ]

    @staticmethod
    def _normalize_symbol(symbol: Optional[str]) -> Optional[str]:
        if not symbol:
            return symbol
        symbol = symbol.strip().upper()
        if symbol.startswith(("SH", "SZ", "BJ")):
            symbol = symbol[2:]
        return symbol

    @staticmethod
    def _normalize_date(date_str: Optional[str]) -> Optional[str]:
        if not date_str:
            return date_str
        value = date_str.strip()
        if "-" in value:
            value = value.replace("-", "")
        return value

    @staticmethod
    def _normalize_period(period: Optional[str]) -> str:
        if not period:
            return "daily"
        value = period.strip().lower()
        if value in {"1d", "d", "day", "daily"}:
            return "daily"
        if value in {"1w", "w", "week", "weekly"}:
            return "weekly"
        if value in {"1m", "m", "month", "monthly"}:
            return "monthly"
        match = re.fullmatch(r"(\d+)\s*(month|months|mo|m)", value)
        if match:
            months = int(match.group(1))
            if months >= 2:
                return "daily"
        if value.endswith("mo") or value.endswith("m"):
            return "monthly"
        return value

    @staticmethod
    def _clean_keywords(keywords: List[str]) -> List[str]:
        cleaned: List[str] = []
        for kw in keywords:
            if not kw:
                continue
            text = str(kw).strip()
            if not text:
                continue
            if "http" in text.lower() or "ok" in text.lower():
                continue
            cleaned.append(text)
        return cleaned

    def _call_tool(self, name: str, args: Dict[str, Any]) -> Any:
        cache_key = f"{name}:{json.dumps(args, sort_keys=True, ensure_ascii=False)}"
        if cache_key in self._tool_cache:
            logger.info("主控: 使用缓存工具结果, name=%s", name)
            return self._tool_cache[cache_key]
        logger.info("主控: 调用子Agent工具, name=%s, args=%s", name, args)
        if name == "get_stock_analysis":
            symbol = self._normalize_symbol(args.get("symbol"))
            start_date = self._normalize_date(args.get("start_date"))
            end_date = self._normalize_date(args.get("end_date"))
            period = self._normalize_period(args.get("period"))
            result = self.stock_agent.analyze_daily_hist(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                period=period,
                adjust=args.get("adjust", ""),
            )
            logger.info("主控: 子Agent返回, name=%s, keys=%s", name, list(result.keys()))
            self._tool_cache[cache_key] = result
            return result
        if name == "get_stock_history":
            symbol = self._normalize_symbol(args.get("symbol"))
            start_date = self._normalize_date(args.get("start_date"))
            end_date = self._normalize_date(args.get("end_date"))
            period = self._normalize_period(args.get("period"))
            result = self.stock_agent.fetch_daily_hist(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                period=period,
                adjust=args.get("adjust", ""),
            )
            logger.info("主控: 子Agent返回, name=%s, keys=%s", name, list(result.keys()))
            self._tool_cache[cache_key] = result
            return result
        if name == "get_stock_summary":
            symbol = self._normalize_symbol(args.get("symbol"))
            result = self.stock_agent.summarize(symbol=symbol)
            logger.info("主控: 子Agent返回, name=%s, keys=%s", name, list(result.keys()))
            self._tool_cache[cache_key] = result
            return result
        if name == "get_stock_tech":
            symbol = self._normalize_symbol(args.get("symbol"))
            start_date = self._normalize_date(args.get("start_date"))
            end_date = self._normalize_date(args.get("end_date"))
            period = self._normalize_period(args.get("period"))
            result = self.stock_agent.analyze_technical_indicators(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                period=period,
                adjust=args.get("adjust", ""),
            )
            logger.info("主控: 子Agent返回, name=%s, keys=%s", name, list(result.keys()))
            self._tool_cache[cache_key] = result
            return result
        if name == "get_sse_summary":
            result = self.stock_agent.fetch_sse_summary()
            logger.info("主控: 子Agent返回, name=%s, rows=%s", name, result.get("rows"))
            self._tool_cache[cache_key] = result
            return result
        if name == "get_szse_summary":
            date = self._normalize_date(args.get("date"))
            result = self.stock_agent.fetch_szse_summary(date=date)
            logger.info("主控: 子Agent返回, name=%s, rows=%s", name, result.get("rows"))
            self._tool_cache[cache_key] = result
            return result
        if name == "get_sse_deal_daily":
            date = self._normalize_date(args.get("date"))
            result = self.stock_agent.fetch_sse_deal_daily(date=date)
            logger.info("主控: 子Agent返回, name=%s, rows=%s", name, result.get("rows"))
            self._tool_cache[cache_key] = result
            return result
        if name == "get_relevant_titles":
            keywords = self._clean_keywords(args.get("keywords", []))
            result = self.news_agent.get_relevant_titles(
                keywords=keywords,
                limit=args.get("limit"),
                web_limit=args.get("web_limit", 5),
            )
            logger.info("主控: 子Agent返回, name=%s, keys=%s", name, list(result.keys()))
            self._tool_cache[cache_key] = result
            return result
        if name == "web_search":
            query = args.get("query")
            limit = args.get("limit", 5)
            result = self.news_agent.search_web_by_keywords([query], web_limit=limit)
            logger.info("主控: 子Agent返回, name=%s, count=%s", name, len(result))
            self._tool_cache[cache_key] = result
            return result
        return {"error": f"unknown tool: {name}"}

    def run(self, user_query: str) -> str:
        tool_results = self.run_tools(user_query)
        summary_prompt = (
            "请基于以下工具结果进行总结，先说明数据覆盖情况（缺失要说明原因），"
            "再输出摘要、数据要点、风险提示。若工具结果为空或报错，不要编造。"
        )
        summary_messages = [
            {"role": "system", "content": summary_prompt},
            {"role": "user", "content": user_query},
            {"role": "user", "content": json.dumps(tool_results, ensure_ascii=False)},
        ]
        final_response = self.client.chat.completions.create(
            model=self.model,
            messages=summary_messages,
        )
        return final_response.choices[0].message.content or ""

    def run_tools(self, user_query: str) -> List[Dict[str, Any]]:
        """
        仅负责工具选择与调用，返回工具结果
        """
        self._tool_cache = {}
        system_prompt = (
            "你是主控 Agent，负责判断需要调用哪些工具获取数据。"
            "不要重复调用相同工具。"
            "若用户要求市场复盘或整体表现，可优先调用交易所统计类工具。"
            "只有在明确需要区间走势或长期分析时，才调用历史行情/技术指标工具。"
        )

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query},
        ]

        tools = self._tools()
        tool_results: List[Dict[str, Any]] = []

        for _ in range(4):
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
            )

            message = response.choices[0].message
            if not message.tool_calls:
                return tool_results

            messages.append({
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": message.tool_calls,
            })

            for tool_call in message.tool_calls:
                name = tool_call.function.name
                args = json.loads(tool_call.function.arguments or "{}")
                result = self._call_tool(name, args)
                tool_results.append({
                    "name": name,
                    "args": args,
                    "result": result,
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result, ensure_ascii=False),
                })

        return tool_results
