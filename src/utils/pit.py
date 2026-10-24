#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Point-in-Time（PIT）上下文

回测时通过 contextvar 设置决策时点，数据层与证据台账据此过滤未来数据。
不使用环境变量，避免多线程回测互相污染。
"""

from __future__ import annotations

import re
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from typing import Iterator, Optional

_AS_OF: ContextVar[Optional[str]] = ContextVar("pit_as_of", default=None)
_BLOCK_NEWS: ContextVar[bool] = ContextVar("pit_block_news", default=False)

_DATE_RE = re.compile(r"(\d{4})[-/年]?(\d{1,2})[-/月]?(\d{1,2})")


def set_as_of(value: Optional[str]) -> None:
    _AS_OF.set(value)


def get_as_of() -> Optional[str]:
    """当前决策时点（YYYY-MM-DD），非回测模式返回 None"""
    return _AS_OF.get()


@contextmanager
def pit_mode(as_of: Optional[str], block_news: Optional[bool] = None) -> Iterator[None]:
    """
    在 with 块内启用 PIT 模式。

    block_news=None 时保持当前设置，便于嵌套（外层回测设置一次即可）。
    """
    token = _AS_OF.set(as_of)
    news_token = _BLOCK_NEWS.set(bool(block_news)) if block_news is not None else None
    try:
        yield
    finally:
        _AS_OF.reset(token)
        if news_token is not None:
            _BLOCK_NEWS.reset(news_token)


def news_blocked() -> bool:
    """回测模式下新闻类数据源不可用（无法 PIT）"""
    return _BLOCK_NEWS.get()


def parse_date(value: Optional[str]) -> Optional[datetime]:
    """解析常见日期格式（YYYY-MM-DD / YYYYMMDD / ISO / YYYY年M月D日）"""
    if not value:
        return None
    text = str(value).strip()
    match = _DATE_RE.search(text)
    if match:
        year, month, day = (int(x) for x in match.groups())
        try:
            return datetime(year, month, day)
        except ValueError:
            return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


def is_after(source_time: Optional[str], as_of: Optional[str]) -> bool:
    """来源时间是否晚于决策时点（无法解析时视为不晚于，避免误杀）"""
    src = parse_date(source_time)
    ref = parse_date(as_of)
    if src is None or ref is None:
        return False
    return src.date() > ref.date()


def as_of_compact(value: Optional[str] = None) -> Optional[str]:
    """返回 YYYYMMDD（供 tushare 接口使用）"""
    ref = parse_date(value or get_as_of())
    return ref.strftime("%Y%m%d") if ref else None
