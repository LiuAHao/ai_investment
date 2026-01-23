#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RSS 新闻解析器测试程序
"""

from news_api import get_news_titles


def main():
    titles = get_news_titles(limit=20)
    print("获取标题数量:", len(titles))
    for i, title in enumerate(titles, 1):
        print(f"{i}. {title}")


if __name__ == "__main__":
    main()
