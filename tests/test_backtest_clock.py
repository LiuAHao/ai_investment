#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""回测时钟测试（注入日历，不联网）"""

from __future__ import annotations

from backtest.clock import TradingClock

CALENDAR = [
    "2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09",
    "2026-01-12", "2026-01-13", "2026-01-14", "2026-01-15", "2026-01-16",
]


def test_next_trading_day_strictly_after():
    clock = TradingClock(calendar=CALENDAR)
    assert clock.next_trading_day("2026-01-05").isoformat() == "2026-01-06"
    assert clock.next_trading_day("2026-01-09").isoformat() == "2026-01-12"
    assert clock.next_trading_day("2026-01-16") is None


def test_execution_date_is_t_plus_one():
    clock = TradingClock(calendar=CALENDAR)
    assert clock.execution_date("2026-01-05") == "2026-01-06"


def test_execution_date_skips_suspended():
    clock = TradingClock(
        calendar=CALENDAR,
        suspended=["2026-01-06", "2026-01-07"],
    )
    assert clock.execution_date("2026-01-05") == "2026-01-08"


def test_execution_date_skips_limit_up_for_buy():
    clock = TradingClock(calendar=CALENDAR, limit_up=["2026-01-06"])
    assert clock.execution_date("2026-01-05", side="buy") == "2026-01-07"
    # 卖出不受涨停限制
    assert clock.execution_date("2026-01-05", side="sell") == "2026-01-06"


def test_execution_date_returns_none_when_delayed_too_long():
    clock = TradingClock(
        calendar=CALENDAR,
        suspended=["2026-01-06", "2026-01-07", "2026-01-08"],
    )
    assert clock.execution_date("2026-01-05", max_delay=1) is None


def test_holding_end_counts_trading_days():
    clock = TradingClock(calendar=CALENDAR)
    assert clock.holding_end("2026-01-06", 3) == "2026-01-09"


def test_weekday_fallback_without_calendar():
    clock = TradingClock()
    # 2026-01-09 是周五
    assert clock.next_trading_day("2026-01-09").isoformat() == "2026-01-12"
