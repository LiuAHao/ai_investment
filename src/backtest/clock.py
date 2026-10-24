#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
回测时钟（纯逻辑）

负责：交易日历、T+1 成交、停牌/涨跌停顺延、持有期计算。
所有方法可注入 calendar / 异常集合，便于单测（不需要联网）。
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Set


def _to_date(value: Any) -> Optional[date]:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value or "").strip()
    if not text:
        return None
    text = text[:10].replace("/", "-")
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(text.replace("-", "") if fmt == "%Y%m%d" else text, fmt).date()
        except ValueError:
            continue
    return None


def _iso(value: Optional[date]) -> Optional[str]:
    return value.isoformat() if value else None


class TradingClock:
    """交易日历与成交规则"""

    def __init__(
        self,
        calendar: Optional[Iterable[Any]] = None,
        suspended: Optional[Iterable[Any]] = None,
        limit_up: Optional[Iterable[Any]] = None,
        limit_down: Optional[Iterable[Any]] = None,
        fallback_weekdays: bool = True,
        source: str = "injected",
    ):
        self._calendar: List[date] = sorted(
            {d for d in (_to_date(x) for x in (calendar or [])) if d}
        )
        self._calendar_set: Set[date] = set(self._calendar)
        self._suspended: Set[date] = {d for d in (_to_date(x) for x in (suspended or [])) if d}
        self._limit_up: Set[date] = {d for d in (_to_date(x) for x in (limit_up or [])) if d}
        self._limit_down: Set[date] = {d for d in (_to_date(x) for x in (limit_down or [])) if d}
        self._fallback = fallback_weekdays
        self._source = "tushare" if source == "tushare" else ("injected" if self._calendar else "weekday_fallback")

    # ---------- 构造 ----------

    @classmethod
    def from_tushare(
        cls,
        start: str,
        end: str,
        exchange: str = "SSE",
    ) -> "TradingClock":
        """从 tushare 交易日历构建；失败时退回工作日近似"""
        try:
            from data.tushare_client import get_trade_calendar

            df = get_trade_calendar(start_date=start, end_date=end, exchange=exchange, limit=2000)
            if df is not None and not df.empty and "cal_date" in df.columns:
                return cls(calendar=df["cal_date"].tolist(), source="tushare")
        except Exception:  # noqa: BLE001
            pass
        return cls()

    # ---------- 基础 ----------

    def is_trading_day(self, value: Any) -> bool:
        day = _to_date(value)
        if day is None:
            return False
        if self._calendar_set:
            return day in self._calendar_set
        if not self._fallback:
            return False
        return day.weekday() < 5

    def next_trading_day(self, value: Any) -> Optional[date]:
        """严格晚于 value 的第一个交易日"""
        day = _to_date(value)
        if day is None:
            return None
        if self._calendar:
            for candidate in self._calendar:
                if candidate > day:
                    return candidate
            return None
        candidate = day + timedelta(days=1)
        for _ in range(14):
            if self.is_trading_day(candidate):
                return candidate
            candidate += timedelta(days=1)
        return None

    def add_trading_days(self, value: Any, count: int) -> Optional[date]:
        """按交易日数量向前推进（count=0 返回当日或下一个交易日）"""
        day = _to_date(value)
        if day is None:
            return None
        current: Optional[date] = day if self.is_trading_day(day) else self.next_trading_day(day)
        remaining = max(0, int(count))
        while current is not None and remaining > 0:
            current = self.next_trading_day(current)
            remaining -= 1
        return current

    # ---------- 成交规则 ----------

    def execution_date(
        self,
        as_of: Any,
        side: str = "buy",
        max_delay: int = 3,
    ) -> Optional[str]:
        """
        T 日决策 → T+1 成交。停牌或一字涨跌停时顺延，最多顺延 max_delay 个交易日。

        Args:
            as_of: 决策日
            side: buy / sell（买入遇涨停、卖出遇跌停无法成交）
            max_delay: 最大顺延交易日数

        Returns:
            成交日 ISO 字符串；无法成交返回 None
        """
        candidate = self.next_trading_day(as_of)
        for _ in range(max(0, max_delay) + 1):
            if candidate is None:
                return None
            if candidate in self._suspended:
                candidate = self.next_trading_day(candidate)
                continue
            if side == "buy" and candidate in self._limit_up:
                candidate = self.next_trading_day(candidate)
                continue
            if side == "sell" and candidate in self._limit_down:
                candidate = self.next_trading_day(candidate)
                continue
            return _iso(candidate)
        return None

    def holding_end(self, execution_date: Any, horizon_days: int) -> Optional[str]:
        """持有期结束日（按交易日计算）"""
        end = self.add_trading_days(execution_date, horizon_days)
        return _iso(end)

    # ---------- 调试 ----------

    def describe(self) -> Dict[str, Any]:
        return {
            "calendar_days": len(self._calendar),
            "calendar_mode": self._source,
            "suspended": len(self._suspended),
            "limit_up": len(self._limit_up),
            "limit_down": len(self._limit_down),
        }
