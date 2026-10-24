#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""回测指标（纯函数）"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def max_drawdown(equity: pd.Series) -> float:
    if equity is None or len(equity) == 0:
        return 0.0
    running_max = equity.cummax()
    drawdown = equity / running_max - 1
    return float(drawdown.min())


def sharpe_ratio(equity: pd.Series, risk_free: float = 0.0) -> Optional[float]:
    if equity is None or len(equity) < 3:
        return None
    returns = equity.pct_change().dropna()
    if returns.empty or returns.std() == 0:
        return None
    excess = returns - risk_free / TRADING_DAYS
    return float(excess.mean() / returns.std() * np.sqrt(TRADING_DAYS))


def compute_metrics(
    equity: pd.Series,
    trades: List[Dict[str, Any]],
    initial_cash: float,
    benchmark_equity: Optional[pd.Series] = None,
) -> Dict[str, Any]:
    """equity 为逐日总资产序列（索引为日期）"""
    if equity is None or len(equity) == 0:
        return {}
    total_return = float(equity.iloc[-1] / initial_cash - 1)
    periods = max(1, len(equity))
    annual_return = float((1 + total_return) ** (TRADING_DAYS / periods) - 1) if total_return > -1 else -1.0

    closed = [t for t in trades if t.get("pnl") is not None]
    wins = [t for t in closed if t["pnl"] > 0]
    losses = [t for t in closed if t["pnl"] < 0]
    win_rate = len(wins) / len(closed) if closed else None
    gross_win = sum(t["pnl"] for t in wins)
    gross_loss = abs(sum(t["pnl"] for t in losses))
    profit_factor = (gross_win / gross_loss) if gross_loss > 0 else None

    traded_amount = sum(abs(t.get("amount") or 0) for t in trades)
    avg_equity = float(equity.mean()) if len(equity) else initial_cash
    turnover = traded_amount / avg_equity if avg_equity else None

    benchmark_return = None
    alpha = None
    if benchmark_equity is not None and len(benchmark_equity) >= 2:
        benchmark_return = float(benchmark_equity.iloc[-1] / benchmark_equity.iloc[0] - 1)
        alpha = total_return - benchmark_return

    return {
        "total_return": total_return,
        "annual_return": annual_return,
        "max_drawdown": max_drawdown(equity),
        "sharpe": sharpe_ratio(equity),
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "trades": len(closed),
        "turnover": turnover,
        "benchmark_return": benchmark_return,
        "alpha": alpha,
        "final_equity": float(equity.iloc[-1]),
    }
