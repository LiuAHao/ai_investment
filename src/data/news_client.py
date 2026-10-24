#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
新闻客户端（多源）

优先级：
1. 网页搜索（ddgs，按关键词）
2. ddgs 网页搜索（关键词兜底，可能无发布时间）

所有条目统一返回 title / link / snippet / published_at / source_domain，
下游据此做时效性判断（无发布时间的来源置信度会被降级）。
"""

from __future__ import annotations

import logging
import re
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from utils.web_search import search_web

logger = logging.getLogger(__name__)

_CACHE: Dict[Tuple[str, int], Tuple[float, List[Dict[str, str]]]] = {}
_CACHE_LOCK = threading.Lock()
_CACHE_TTL = int(600)

_CODE_RE = re.compile(r"^\d{6}$")


class NewsAgent:
    """新闻检索（多源 + 缓存）"""

    def __init__(self, default_limit: int = 50, cache_seconds: int = 600):
        self.default_limit = default_limit
        self.cache_seconds = cache_seconds

    def get_relevant_titles(
        self,
        keywords: List[str],
        limit: Optional[int] = None,
        web_limit: int = 5,
        as_of: Optional[str] = None,
    ) -> Dict:
        """
        获取并筛选相关新闻。

        Returns:
            {timestamp, total_titles, relevant_titles, web_results, source}
        """
        keywords = [str(k) for k in (keywords or []) if k]
        limit = int(limit or web_limit or 5)

        results: List[Dict[str, str]] = []
        sources: List[str] = []

        # ddgs 网页搜索
        if len(results) < limit:
            query = " ".join(keywords)
            web = search_web(f"{query} 新闻" if query else "A股 财经 新闻", max_results=limit)
            results.extend(_with_meta(item, "web") for item in web)
            if web:
                sources.append("web")

        results = [item for item in results if not _is_navigation(item.get("title", ""))]
        results = self._filter_as_of(results, as_of)
        deduped = self._deduplicate(results)
        sorted_results = self._sort_by_relevance(deduped, keywords)[:limit]

        return {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "total_titles": len(sorted_results),
            "relevant_titles": [item["title"] for item in sorted_results if item.get("title")],
            "web_results": sorted_results,
            "source": ",".join(sources),
        }

    def search_web_by_keywords(self, keywords: List[str], web_limit: int = 5) -> List[Dict[str, str]]:
        query = " ".join([kw for kw in keywords if kw])
        results = search_web(f"{query} 新闻" if query else "A股 财经 新闻", max_results=web_limit)
        return [_with_meta(item, "web") for item in results]

    def fetch_titles_with_web(
        self,
        limit: Optional[int] = None,
        web_limit: int = 5,
        web_query: Optional[str] = None,
    ) -> Dict:
        query = web_query or "A股 财经 新闻 最新"
        return {"web_query": query, "web_results": self.search_web_by_keywords([query], web_limit)}

    # ---------- 结构化新闻源 ----------

    def _filter_as_of(self, results: List[Dict[str, str]], as_of: Optional[str]) -> List[Dict[str, str]]:
        """PIT：丢弃晚于决策时点的新闻"""
        if not as_of:
            return results
        cutoff = str(as_of)[:10]
        filtered = []
        for item in results:
            published = str(item.get("published_at") or "")[:10]
            if published and published > cutoff:
                continue
            filtered.append(item)
        return filtered

    @staticmethod
    def _deduplicate(results: List[Dict[str, str]]) -> List[Dict[str, str]]:
        seen = set()
        output = []
        for item in results:
            key = (item.get("title") or "").strip().lower()
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
        if not keywords:
            return results

        def score(item: Dict[str, str]) -> int:
            text = f"{item.get('title', '')} {item.get('snippet', '')}".lower()
            return sum(text.count(kw.lower()) for kw in keywords if kw)

        return sorted(results, key=score, reverse=True)


def _with_meta(item: Dict[str, str], source: str) -> Dict[str, str]:
    link = item.get("link") or ""
    return {
        "title": item.get("title") or "",
        "link": link,
        "snippet": item.get("snippet") or "",
        "published_at": item.get("published_at") or "",
        "source_domain": item.get("source_domain") or _domain(link) or source,
    }


def _domain(link: str) -> str:
    try:
        from urllib.parse import urlparse

        return urlparse(link).netloc
    except Exception:
        return ""


def _cache_get(key: Tuple[str, int]) -> Optional[List[Dict[str, str]]]:
    with _CACHE_LOCK:
        entry = _CACHE.get(key)
        if not entry:
            return None
        ts, value = entry
        if time.time() - ts > _CACHE_TTL:
            _CACHE.pop(key, None)
            return None
        return value


def _cache_set(key: Tuple[str, int], value: List[Dict[str, str]]) -> None:
    with _CACHE_LOCK:
        if len(_CACHE) >= 128:
            _CACHE.clear()
        _CACHE[key] = (time.time(), value)


# ==================== 噪音过滤 ====================

_NAV_TITLE_MARKERS = (
    "新闻公告_个股行情",
    "财经首页",
    "股票首页",
    "行情中心",
    "东方财富网",
    "同花顺财经",
    "_新浪财经",
    "股票频道",
    "个股行情",
)


def _is_navigation(title: str) -> bool:
    """过滤搜索结果里的站点导航页标题"""
    text = (title or "").strip()
    if not text:
        return True
    return any(marker in text for marker in _NAV_TITLE_MARKERS)
