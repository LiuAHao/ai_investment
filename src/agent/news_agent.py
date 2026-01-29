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
        web_results = self.search_web_by_keywords(keywords, web_limit=web_limit)
        return {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "total_titles": 0,
            "relevant_titles": [],
            "web_results": web_results,
        }
