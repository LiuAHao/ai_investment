#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""网页检索工具（新闻兜底）"""

from __future__ import annotations

from typing import Any, Dict

from tools.base import BaseTool, CostLevel, RiskLevel


class WebResearchTool(BaseTool):
    name = "web_research"
    description = "网页检索（搜索结果可能无发布时间，仅作新闻来源的兜底）"
    timeout = 20
    asset_types = []
    intents = ["news_analysis", "event_analysis"]
    cost_level = CostLevel.LOW
    risk_level = RiskLevel.LOW

    def execute(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        from utils.web_search import search_web

        try:
            max_results = int(max_results)
        except (TypeError, ValueError):
            max_results = 5
        results = search_web(query, max_results=max_results)
        evidence = [
            {
                "category": "news",
                "statement": f"{item.get('title', '')}：{item.get('snippet', '')[:120]}",
                "source_url": item.get("link", ""),
                "source_time": item.get("published_at", ""),
                "caliber": "网页搜索/无发布时间" if not item.get("published_at") else "网页搜索",
                "confidence": 0.6 if item.get("published_at") else 0.4,
            }
            for item in results
        ]
        return {
            "query": query,
            "source": "web",
            "results": results,
            "evidence": evidence,
            "summary": f"网页检索「{query}」返回 {len(results)} 条",
        }
