#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
联网搜索工具
"""

from typing import List, Dict, Optional
import logging
import os
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@contextmanager
def _without_proxy(enabled: bool):
    if not enabled:
        yield
        return
    proxy_keys = [
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ]
    backup = {key: os.environ.get(key) for key in proxy_keys if os.environ.get(key)}
    for key in proxy_keys:
        os.environ.pop(key, None)
    try:
        yield
    finally:
        for key, value in backup.items():
            os.environ[key] = value


def search_web(query: str, max_results: int = 5, region: Optional[str] = None) -> List[Dict[str, str]]:
    """
    使用 DuckDuckGo 进行联网搜索

    Args:
        query: 搜索关键词
        max_results: 返回结果数量

    Returns:
        搜索结果列表
    """
    if not query:
        return []

    try:
        from ddgs import DDGS
    except Exception:
        try:
            from duckduckgo_search import DDGS
        except Exception as e:
            logger.warning("联网搜索不可用: %s", e)
            return []

    results: List[Dict[str, str]] = []
    disable_proxy = os.getenv("DDGS_DISABLE_PROXY", "0") == "1"
    use_region = region or os.getenv("DDGS_REGION") or "cn-zh"

    try:
        with _without_proxy(disable_proxy), DDGS() as ddgs:
            for item in ddgs.text(query, max_results=max_results, region=use_region):
                if not item:
                    continue
                results.append({
                    "title": item.get("title") or "",
                    "link": item.get("href") or item.get("url") or "",
                    "snippet": item.get("body") or item.get("snippet") or "",
                })
    except Exception as e:
        logger.error("联网搜索失败: %s", e)
        return []

    return results