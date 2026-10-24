#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PIT 数据源上下文

回测时设置决策时点，并禁用无法 point-in-time 的新闻/公告/网页工具。
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Optional

from utils import pit


@contextmanager
def pit_datasource(as_of: str, allow_news: bool = False) -> Iterator[None]:
    """
    回测数据源上下文。

    Args:
        as_of: 决策时点（YYYY-MM-DD）
        allow_news: 是否允许新闻类工具（默认 False，因为无法可靠 PIT）
    """
    with pit.pit_mode(as_of, block_news=not allow_news):
        yield


def current_as_of() -> Optional[str]:
    return pit.get_as_of()


def news_available() -> bool:
    return not pit.news_blocked()
