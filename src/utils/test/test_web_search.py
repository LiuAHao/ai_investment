#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
联网搜索测试脚本
"""

import os
import sys

CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_SRC = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
if PROJECT_SRC not in sys.path:
    sys.path.insert(0, PROJECT_SRC)

from utils.web_search import search_web


def main() -> None:
    query = "2026年1月29日 A股 复盘 上证指数 深证成指 创业板指"
    results = search_web(query, max_results=5, region="cn-zh")
    if not results:
        os.environ["DDGS_DISABLE_PROXY"] = "1"
        results = search_web(query, max_results=5, region="wt-wt")
    print("搜索关键词:", query)
    print("结果数量:", len(results))
    for idx, item in enumerate(results, start=1):
        print(f"\n[{idx}] {item.get('title')}")
        print(item.get("link"))
        snippet = item.get("snippet") or ""
        print(snippet.strip()[:200])


if __name__ == "__main__":
    main()
