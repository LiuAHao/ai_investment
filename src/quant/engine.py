#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
轻量量化回测引擎（日线、只做多、T+1 开盘成交）

规则：
- T 日收盘产生信号，T+1 开盘成交
- A 股 100 股一手，不足一手不买
- 手续费双边（默认万 2.5，最低 5 元）+ 滑点（默认 0.1%）
- 最后一日收盘强制平仓，保证收益完整
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import pandas as pd

from quant.metrics import compute_metrics
from quant.strategies import DEFAULT_PARAMS, StrategyFn, get_strategy


@dataclass
class QuantResult:
    symbol: str
    strategy: str
    equity: pd.Series
    trades: List[Dict[str, Any]]
    metrics: Dict[str, Any]
    params: Dict[str, Any] = field(default_factory=dict)


def _fee(amount: float, fee_rate: float, min_fee: float) -> float:
    return max(abs(amount) * fee_rate, min_fee) if amount else 0.0


def run_backtest(
    df: pd.DataFrame,
    signals: pd.Series,
    symbol: str = "",
    strategy: str = "",
    cash: float = 1_000_000.0,
    fee_rate: float = 0.00025,
    min_fee: float = 5.0,
    slippage: float = 0.001,
    lot: int = 100,
    close_at_end: bool = True,
    params: Optional[Dict[str, Any]] = None,
) -> QuantResult:
    """单标的回测。signals 为 0/1 目标仓位序列（与 df 等长）"""
    if df is None or df.empty:
        raise ValueError("行情数据为空")
    signals = signals.reset_index(drop=True)
    if len(signals) != len(df):
        raise ValueError("信号长度与行情不一致")

    cash_balance = float(cash)
    shares = 0
    entry_cost = 0.0
    trades: List[Dict[str, Any]] = []
    equity_values: List[float] = []
    dates = pd.to_datetime(df["date"])

    def sell(price: float, date: Any, reason: str) -> None:
        nonlocal cash_balance, shares, entry_cost
        amount = shares * price
        fee = _fee(amount, fee_rate, min_fee)
        cash_balance += amount - fee
        pnl = amount - fee - entry_cost
        trades.append({
            "date": str(pd.Timestamp(date).date()),
            "side": "sell",
            "price": round(price, 4),
            "shares": shares,
            "amount": round(amount, 2),
            "fee": round(fee, 2),
            "pnl": round(pnl, 2),
            "reason": reason,
        })
        shares = 0
        entry_cost = 0.0

    for i in range(len(df)):
        open_price = float(df["open"].iloc[i])
        close_price = float(df["close"].iloc[i])
        target = int(signals.iloc[i - 1]) if i > 0 else 0

        if target == 1 and shares == 0 and open_price > 0:
            price = open_price * (1 + slippage)
            affordable = int((cash_balance - min_fee) // (price * lot)) * lot
            while affordable > 0:
                amount = affordable * price
                if amount + _fee(amount, fee_rate, min_fee) <= cash_balance:
                    break
                affordable -= lot
            if affordable > 0:
                amount = affordable * price
                fee = _fee(amount, fee_rate, min_fee)
                cash_balance -= amount + fee
                shares = affordable
                entry_cost = amount + fee
                trades.append({
                    "date": str(pd.Timestamp(dates.iloc[i]).date()),
                    "side": "buy",
                    "price": round(price, 4),
                    "shares": shares,
                    "amount": round(amount, 2),
                    "fee": round(fee, 2),
                    "pnl": None,
                    "reason": "signal",
                })
        elif target == 0 and shares > 0 and open_price > 0:
            sell(open_price * (1 - slippage), dates.iloc[i], "signal")

        equity_values.append(cash_balance + shares * close_price)

    if close_at_end and shares > 0:
        last_price = float(df["close"].iloc[-1]) * (1 - slippage)
        sell(last_price, dates.iloc[-1], "close_at_end")
        equity_values[-1] = cash_balance

    equity = pd.Series(equity_values, index=dates, name="equity")
    metrics = compute_metrics(equity, trades, float(cash))
    return QuantResult(
        symbol=symbol,
        strategy=strategy,
        equity=equity,
        trades=trades,
        metrics=metrics,
        params=params or {},
    )


def run_portfolio(
    frames: Dict[str, pd.DataFrame],
    strategy: str = "ma_cross",
    strategy_params: Optional[Dict[str, Any]] = None,
    cash: float = 1_000_000.0,
    fee_rate: float = 0.00025,
    min_fee: float = 5.0,
    slippage: float = 0.001,
    benchmark_equity: Optional[pd.Series] = None,
    custom_strategy: Optional[StrategyFn] = None,
) -> QuantResult:
    """
    多标的等权组合：资金按标的数量均分，各自独立回测后合并净值。
    """
    if not frames:
        raise ValueError("资产列表为空")
    strategy_params = {**DEFAULT_PARAMS.get(strategy, {}), **(strategy_params or {})}
    per_cash = float(cash) / len(frames)
    results: List[QuantResult] = []
    for symbol, df in frames.items():
        signals = (
            custom_strategy(df, **strategy_params)
            if custom_strategy is not None
            else get_strategy(strategy)(df, **strategy_params)
        )
        results.append(run_backtest(
            df=df,
            signals=signals,
            symbol=symbol,
            strategy=strategy,
            cash=per_cash,
            fee_rate=fee_rate,
            min_fee=min_fee,
            slippage=slippage,
            params=strategy_params,
        ))

    equity_frame = pd.concat({r.symbol: r.equity for r in results}, axis=1).sort_index()
    for column in equity_frame.columns:
        equity_frame[column] = equity_frame[column].ffill().fillna(per_cash)
    combined = equity_frame.sum(axis=1)

    all_trades: List[Dict[str, Any]] = []
    for result in results:
        for trade in result.trades:
            all_trades.append({**trade, "symbol": result.symbol})
    all_trades.sort(key=lambda item: item["date"])

    benchmark = None
    if benchmark_equity is not None and len(benchmark_equity) > 0:
        benchmark = (
            benchmark_equity
            .reindex(combined.index)
            .ffill()
            .bfill()
            .apply(lambda value: value / benchmark_equity.iloc[0] * cash)
        )

    metrics = compute_metrics(combined, all_trades, float(cash), benchmark)
    return QuantResult(
        symbol=",".join(frames.keys()),
        strategy=strategy,
        equity=combined,
        trades=all_trades,
        metrics=metrics,
        params=strategy_params,
    )
