#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
联网搜索工具

改造点：
1. 去掉进程级全局锁，改为信号量限流（并行 Agent 不再互相饿死）
2. 增加结果缓存（同一查询在多个 Agent 中只打一次网络）
3. 返回结构补齐 source_domain / published_at 字段（可能为空）
"""

from __future__ import annotations

import logging
import os
import threading
import time
from contextlib import contextmanager
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# DDGS 并发能力有限，用信号量限流而不是全局串行
_SEARCH_SEMAPHORE = threading.Semaphore(int(os.getenv("DDGS_CONCURRENCY", "3")))

_CACHE: Dict[Tuple[str, int, str], Tuple[float, List[Dict[str, str]]]] = {}
_CACHE_LOCK = threading.Lock()
_CACHE_TTL = int(os.getenv("SEARCH_CACHE_TTL_SECONDS", "600"))
_CACHE_MAX = 256


@contextmanager
def _without_proxy(enabled: bool):
    if not enabled:
        yield
        return
    proxy_keys = [
        "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
        "http_proxy", "https_proxy", "all_proxy",
    ]
    backup = {key: os.environ.get(key) for key in proxy_keys if os.environ.get(key)}
    for key in proxy_keys:
        os.environ.pop(key, None)
    try:
        yield
    finally:
        for key, value in backup.items():
            os.environ[key] = value


def search_web(
    query: str,
    max_results: int = 5,
    region: Optional[str] = None,
) -> List[Dict[str, str]]:
    """使用 DuckDuckGo 搜索（带缓存与并发限流）"""
    if not query:
        return []
    try:
        max_results = int(max_results)
    except (TypeError, ValueError):
        max_results = 5
    use_region = region or os.getenv("DDGS_REGION") or "cn-zh"

    cache_key = (query, max_results, use_region)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        from ddgs import DDGS
    except Exception:
        try:
            from duckduckgo_search import DDGS
        except Exception as exc:  # noqa: BLE001
            logger.warning("联网搜索不可用: %s", exc)
            return []

    disable_proxy = os.getenv("DDGS_DISABLE_PROXY", "0") == "1"
    try:
        ddgs_timeout = int(os.getenv("DDGS_TIMEOUT", "10"))
    except (TypeError, ValueError):
        ddgs_timeout = 10
    try:
        lock_timeout = int(os.getenv("DDGS_LOCK_TIMEOUT", "15"))
    except (TypeError, ValueError):
        lock_timeout = 15

    if not _SEARCH_SEMAPHORE.acquire(timeout=max(1, lock_timeout)):
        logger.warning("联网搜索并发已满（>%ss），跳过本次查询", lock_timeout)
        return []

    results: List[Dict[str, str]] = []
    try:
        with _without_proxy(disable_proxy), DDGS(timeout=ddgs_timeout) as ddgs:
            for item in ddgs.text(query, max_results=max_results, region=use_region):
                if not item:
                    continue
                link = item.get("href") or item.get("url") or ""
                results.append({
                    "title": item.get("title") or "",
                    "link": link,
                    "snippet": item.get("body") or item.get("snippet") or "",
                    "published_at": item.get("published") or item.get("date") or "",
                    "source_domain": _domain(link),
                })
    except Exception as exc:  # noqa: BLE001
        logger.error("联网搜索失败: %s", exc)
        return []
    finally:
        _SEARCH_SEMAPHORE.release()

    _cache_set(cache_key, results)
    return results


def _domain(link: str) -> str:
    try:
        from urllib.parse import urlparse

        return urlparse(link).netloc
    except Exception:
        return ""


def _cache_get(key: Tuple[str, int, str]) -> Optional[List[Dict[str, str]]]:
    with _CACHE_LOCK:
        entry = _CACHE.get(key)
        if not entry:
            return None
        ts, value = entry
        if time.time() - ts > _CACHE_TTL:
            _CACHE.pop(key, None)
            return None
        return value


def _cache_set(key: Tuple[str, int, str], value: List[Dict[str, str]]) -> None:
    with _CACHE_LOCK:
        if len(_CACHE) >= _CACHE_MAX:
            _CACHE.clear()
        _CACHE[key] = (time.time(), value)
