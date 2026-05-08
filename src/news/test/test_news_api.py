#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RSS 新闻解析器测试程序
"""

import os
import sys

CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))
NEWS_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if NEWS_DIR not in sys.path:
    sys.path.insert(0, NEWS_DIR)

from news_api import get_news_titles


def main():
    titles = get_news_titles(limit=20)
    print("获取标题数量:", len(titles))
    for i, title in enumerate(titles, 1):
        print(f"{i}. {title}")


if __name__ == "__main__":
    main()
