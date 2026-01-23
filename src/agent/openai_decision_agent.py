#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
基于 OpenAI 接口的最小化智能决策 Agent
"""

import json
import os
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


class OpenAIDecisionAgent:
    """最小化主控 Agent（OpenAI Function Calling）"""

    def __init__(self, model: Optional[str] = None):
        self.client = _build_client()
        self.model = model or _get_env("OPENAI_MODEL") or _get_env("DEEPSEEK_MODEL") or "deepseek-chat"
        self.news_agent = NewsAgent()
        self.stock_agent = StockAgent()

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
                    "name": "get_news_titles",
                    "description": "获取最新新闻标题",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "limit": {"type": "integer"}
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
        ]

    @staticmethod
    def _normalize_symbol(symbol: Optional[str]) -> Optional[str]:
        if not symbol:
            return symbol
        symbol = symbol.strip().upper()
        if "." in symbol:
            symbol = symbol.split(".", 1)[0]
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
            return result
        if name == "get_news_titles":
            result = self.news_agent.fetch_titles(limit=args.get("limit"))
            logger.info("主控: 子Agent返回, name=%s, count=%s", name, len(result))
            return result
        if name == "get_relevant_titles":
            keywords = self._clean_keywords(args.get("keywords", []))
            result = self.news_agent.get_relevant_titles(
                keywords=keywords,
                limit=args.get("limit"),
            )
            logger.info("主控: 子Agent返回, name=%s, keys=%s", name, list(result.keys()))
            return result
        return {"error": f"unknown tool: {name}"}

    def run(self, user_query: str) -> str:
        system_prompt = (
            "你是投资分析助手，必须先调用工具获取数据，再基于数据给出结论。"
            "输出结构化要点：摘要、数据要点、风险提示。"
        )

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query},
        ]

        tools = self._tools()

        for _ in range(4):
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
            )

            message = response.choices[0].message
            if not message.tool_calls:
                return message.content or ""

            messages.append({
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": message.tool_calls,
            })

            for tool_call in message.tool_calls:
                name = tool_call.function.name
                args = json.loads(tool_call.function.arguments or "{}")
                result = self._call_tool(name, args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result, ensure_ascii=False),
                })

        final_response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
        )
        return final_response.choices[0].message.content or ""
