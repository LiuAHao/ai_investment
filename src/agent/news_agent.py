#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
新闻 Agent：获取与筛选新闻标题
"""

from typing import Dict, List, Optional

from datetime import datetime
import logging

logger = logging.getLogger(__name__)

from utils.web_search import search_web


class NewsAgent:
    """新闻 Agent"""

    def __init__(self, default_limit: int = 50, cache_seconds: int = 60):
        self.default_limit = default_limit
        self.cache_seconds = cache_seconds

    def fetch_titles_with_web(
        self,
        limit: Optional[int] = None,
        web_limit: int = 5,
        web_query: Optional[str] = None,
    ) -> Dict:
        """
        获取新闻标题并附带联网搜索结果

        Args:
            limit: RSS 标题数量
            web_limit: 联网搜索结果数量
            web_query: 联网搜索关键词

        Returns:
            RSS 与联网搜索结果
        """
        query = web_query or "A股 财经 新闻 最新"
        web_results = search_web(query, max_results=web_limit)
        return {
            "web_query": query,
            "web_results": web_results,
        }

    def search_web_by_keywords(
        self,
        keywords: List[str],
        web_limit: int = 5,
    ) -> List[Dict[str, str]]:
        """
        按关键词进行联网搜索

        Args:
            keywords: 关键词列表
            web_limit: 返回结果数量

        Returns:
            联网搜索结果列表
        """
        query = " ".join([kw for kw in keywords if kw])
        if query:
            query = f"{query} 新闻"
        return search_web(query, max_results=web_limit)

    def get_relevant_titles(
        self,
        keywords: List[str],
        limit: Optional[int] = None,
        web_limit: int = 5,
    ) -> Dict:
        """
        获取并筛选相关新闻标题

        Args:
            keywords: 关键词列表
            limit: 最多返回标题数量

        Returns:
            结果摘要
        """
        logger.info("新闻Agent: 获取相关新闻, keywords=%s", keywords)
        raw_results = self.search_web_by_keywords(keywords, web_limit=web_limit)

        # 1. 标题去重：归一化后完全相同的条目只保留第一条
        deduped = self._deduplicate(raw_results)

        # 2. 按关键词相关性排序（匹配度高的排前），不删除任何条目
        sorted_results = self._sort_by_relevance(deduped, keywords)

        # 3. 提取标题列表填充 relevant_titles
        relevant_titles = [item["title"] for item in sorted_results if item.get("title")]

        return {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "total_titles": len(sorted_results),
            "relevant_titles": relevant_titles,
            "web_results": sorted_results,
        }

    @staticmethod
    def _deduplicate(results: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """按标题去重，保留第一次出现的条目"""
        seen = set()
        output = []
        for item in results:
            key = item.get("title", "").strip().lower()
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            output.append(item)
        return output

    @staticmethod
    def _sort_by_relevance(
        results: List[Dict[str, str]], keywords: List[str]
    ) -> List[Dict[str, str]]:
        """按关键词在标题+摘要中出现的次数降序排列，不删除任何条目"""
        if not keywords:
            return results

        def score(item: Dict[str, str]) -> int:
            text = f"{item.get('title', '')} {item.get('snippet', '')}".lower()
            return sum(text.count(kw.lower()) for kw in keywords if kw)

        return sorted(results, key=score, reverse=True)
