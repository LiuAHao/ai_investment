#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
决策结算

到期后拉取区间收益与基准 alpha，生成结构化结算结果。
核心计算是纯函数（compute_return / compute_alpha），便于单测；
价格拉取通过 price_fetcher 注入，默认走 DataAgent。
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from memory import decision_store
from utils.pit import parse_date

logger = logging.getLogger(__name__)

HORIZON_DAYS = {
    "short": 5,
    "medium": 20,
    "long": 60,
    "5d": 5,
    "20d": 20,
    "60d": 60,
}

BENCHMARKS = {
    "cn_stock": "000300",
    "etf": "000300",
    "index": "000300",
    "us_stock": "SPX",
    "hk_stock": "HSI",
}


def compute_return(entry_price: float, exit_price: float) -> float:
    """区间简单收益率"""
    if not entry_price:
        return 0.0
    return (exit_price / entry_price) - 1.0


def compute_alpha(stock_return: float, benchmark_return: float) -> float:
    """相对基准超额收益"""
    return stock_return - benchmark_return


def horizon_days(horizon: Optional[str]) -> int:
    return HORIZON_DAYS.get(str(horizon or "medium"), 20)


PriceFetcher = Callable[[str, str, int], Dict[str, float]]


def _default_price_fetcher(symbol: str, start_date: str, days: int) -> Dict[str, float]:
    """
    默认价格拉取（前复权）。

    成交规则：T 日决策 → T+1 开盘买入；持有 N 个交易日后收盘卖出。
    Returns:
        {entry, exit, bars}
    """
    from data.stock_client import DataAgent

    agent = DataAgent()
    start = parse_date(start_date) or datetime.now()
    end = start + timedelta(days=days * 2 + 20)
    df = agent._fetch_hist_with_fallback(
        symbol=symbol,
        start_date=start.strftime("%Y%m%d"),
        end_date=end.strftime("%Y-%m-%d"),
        period="daily",
        adjust="qfq",
    )
    rows = df.to_dict("records") if df is not None and len(df) > 0 else []
    rows = sorted(rows, key=lambda row: str(row.get("日期") or row.get("trade_date") or row.get("date") or ""))
    if len(rows) < 2:
        return {}
    entry = _row_field(rows[1], ("开盘", "open")) or _row_close(rows[0])
    exit_index = min(1 + max(1, days), len(rows) - 1)
    exit_price = _row_close(rows[exit_index])
    if not entry or not exit_price:
        return {}
    return {"entry": entry, "exit": exit_price, "bars": float(len(rows))}


def settle_pending(
    price_fetcher: Optional[PriceFetcher] = None,
    now: Optional[datetime] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """
    扫描到期记录并结算。

    Returns:
        本次成功结算的记录列表
    """
    fetcher = price_fetcher or _default_price_fetcher
    current = now or datetime.now()
    settled: List[Dict[str, Any]] = []

    for record in decision_store.list_unsettled(limit=limit):
        as_of = parse_date(record.get("as_of"))
        if not as_of:
            continue
        days = horizon_days(record.get("horizon"))
        if current < as_of + timedelta(days=days):
            continue

        payload = record.get("payload") or {}
        assets = payload.get("asset_ids") or record.get("asset_ids") or []
        snapshot = payload.get("price_snapshot") or {}
        symbol = str(snapshot.get("symbol") or (assets[0] if assets else ""))
        if not symbol:
            continue

        try:
            prices = fetcher(symbol, as_of.strftime("%Y-%m-%d"), days)
        except Exception as exc:  # noqa: BLE001
            logger.warning("结算取价失败 %s: %s", symbol, exc)
            continue
        if not prices.get("entry") or not prices.get("exit"):
            continue

        ret = compute_return(prices["entry"], prices["exit"])
        benchmark_ret = _benchmark_return(record, as_of, days, fetcher)
        alpha = compute_alpha(ret, benchmark_ret) if benchmark_ret is not None else None

        stance = str(record.get("stance") or "neutral")
        hit = _is_hit(stance, ret)
        settlement = {
            "entry_price": prices["entry"],
            "exit_price": prices["exit"],
            "return": round(ret, 6),
            "benchmark_return": round(benchmark_ret, 6) if benchmark_ret is not None else None,
            "alpha": round(alpha, 6) if alpha is not None else None,
            "hit": hit,
            "horizon_days": days,
            "settled_for": as_of.strftime("%Y-%m-%d"),
        }
        reflection = build_reflection(record, settlement)
        decision_store.update_settlement(record["decision_id"], settlement, reflection.get("text"))
        settled.append({"decision_id": record["decision_id"], **settlement, "reflection": reflection})

    return settled


def build_reflection(record: Dict[str, Any], settlement: Dict[str, Any]) -> Dict[str, Any]:
    """
    生成结构化反思（200 字以内），归因到判断而非归因到市场。
    """
    hit = bool(settlement.get("hit"))
    alpha = settlement.get("alpha")
    stance = record.get("stance") or "neutral"
    payload = record.get("payload") or {}
    falsifiers = (payload.get("verdict") or {}).get("falsifiers_to_watch") or []

    if hit:
        reason = "判断方向与后续走势一致"
    elif alpha is not None and alpha > 0:
        reason = "方向偏差但取得正超额，需要检查是否运气或基准选择问题"
    else:
        reason = "方向与后续走势相反"

    miss_reason = "unforeseen"
    if not hit:
        if payload.get("degraded"):
            miss_reason = "data_gap"
        elif (payload.get("verdict") or {}).get("conviction", 0) >= 0.75:
            miss_reason = "logic_or_overconfidence"
        else:
            miss_reason = "timing_or_unknown"

    text = (
        f"[{record.get('as_of')}] {record.get('query', '')[:40]}："
        f"判断 {stance}，持有 {settlement.get('horizon_days')} 日收益 "
        f"{settlement.get('return', 0):.2%}，超额 "
        f"{(settlement.get('alpha') or 0):.2%}。{reason}。"
    )
    if falsifiers:
        text += f" 观察项：{falsifiers[0][:60]}。"
    return {
        "text": text[:200],
        "hit": hit,
        "alpha": alpha,
        "miss_reason": miss_reason,
    }


def _is_hit(stance: str, ret: float, neutral_band: float = 0.03) -> bool:
    if stance == "bullish":
        return ret > 0
    if stance == "bearish":
        return ret < 0
    return abs(ret) <= neutral_band


def _row_close(row: Any) -> Optional[float]:
    return _row_field(row, ("收盘", "close", "latest_close"))


def _row_field(row: Any, keys: tuple) -> Optional[float]:
    if not isinstance(row, dict):
        return None
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _benchmark_return(
    record: Dict[str, Any],
    as_of: datetime,
    days: int,
    fetcher: PriceFetcher,
) -> Optional[float]:
    payload = record.get("payload") or {}
    benchmark = str(payload.get("benchmark") or "000300")
    try:
        prices = fetcher(benchmark, as_of.strftime("%Y-%m-%d"), days)
    except Exception:  # noqa: BLE001
        return None
    if not prices.get("entry") or not prices.get("exit"):
        return None
    return compute_return(prices["entry"], prices["exit"])
