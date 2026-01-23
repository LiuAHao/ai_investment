#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
新闻 Agent：获取与筛选新闻标题
"""

from typing import Dict, List, Optional

from datetime import datetime
import logging

logger = logging.getLogger(__name__)

from news.news_api import get_news_titles


class NewsAgent:
    """新闻 Agent"""

    def __init__(self, default_limit: int = 50, cache_seconds: int = 60):
        self.default_limit = default_limit
        self.cache_seconds = cache_seconds
        self._cache_titles: List[str] = []
        self._cache_time: Optional[datetime] = None

    def fetch_titles(self, limit: Optional[int] = None) -> List[str]:
        """
        获取新闻标题列表

        Args:
            limit: 最多返回标题数量

        Returns:
            标题列表
        """
        use_limit = limit or self.default_limit
        logger.info("新闻Agent: 获取新闻标题, limit=%s", use_limit)
        if self._cache_time and self._cache_titles:
            delta = (datetime.now() - self._cache_time).total_seconds()
            if delta <= self.cache_seconds:
                logger.info("新闻Agent: 使用缓存, age=%.1fs", delta)
                return self._cache_titles[:use_limit]

        titles = get_news_titles(limit=use_limit)
        logger.info("新闻Agent: 获取标题完成, count=%s", len(titles))
        self._cache_titles = titles
        self._cache_time = datetime.now()
        return titles

    def filter_by_keywords(self, titles: List[str], keywords: List[str]) -> List[Dict]:
        """
        按关键词筛选标题并返回相关度

        Args:
            titles: 标题列表
            keywords: 关键词列表

        Returns:
            含相关度的结果列表
        """
        if not titles or not keywords:
            return []

        results: List[Dict] = []
        for title in titles:
            score = 0
            lower_title = title.lower()
            for kw in keywords:
                if kw.lower() in lower_title:
                    score += 1
            if score > 0:
                results.append({
                    "title": title,
                    "relevance_score": score,
                })

        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        logger.info("新闻Agent: 关键词筛选完成, keywords=%s, matched=%s", keywords, len(results))
        return results

    def get_relevant_titles(self, keywords: List[str], limit: Optional[int] = None) -> Dict:
        """
        获取并筛选相关新闻标题

        Args:
            keywords: 关键词列表
            limit: 最多返回标题数量

        Returns:
            结果摘要
        """
        use_limit = limit or self.default_limit
        logger.info("新闻Agent: 获取相关新闻, keywords=%s, limit=%s", keywords, use_limit)
        titles = self.fetch_titles(limit=use_limit)
        relevant = self.filter_by_keywords(titles, keywords)
        return {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "total_titles": len(titles),
            "relevant_titles": relevant,
        }
