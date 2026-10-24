#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
内置策略

约定：输入日线 DataFrame（含 close），输出与索引对齐的目标仓位 Series（0 或 1）。
信号在 T 日收盘产生，引擎在 T+1 开盘执行。
"""

from __future__ import annotations

from typing import Callable, Dict

import pandas as pd

StrategyFn = Callable[..., pd.Series]


def buy_hold(df: pd.DataFrame, **_: object) -> pd.Series:
    return pd.Series(1, index=df.index, dtype=int)


def ma_cross(df: pd.DataFrame, fast: int = 20, slow: int = 60, **_: object) -> pd.Series:
    """双均线：快线在慢线上方持有"""
    fast = max(2, int(fast))
    slow = max(fast + 1, int(slow))
    fast_ma = df["close"].rolling(fast).mean()
    slow_ma = df["close"].rolling(slow).mean()
    signal = (fast_ma > slow_ma).astype(int)
    signal.iloc[:slow] = 0
    return signal.fillna(0).astype(int)


def momentum(df: pd.DataFrame, lookback: int = 20, **_: object) -> pd.Series:
    """动量：近 N 日收益为正则持有"""
    lookback = max(2, int(lookback))
    ret = df["close"] / df["close"].shift(lookback) - 1
    signal = (ret > 0).astype(int)
    signal.iloc[:lookback] = 0
    return signal.fillna(0).astype(int)


DEFAULT_PARAMS: Dict[str, Dict[str, int]] = {
    "buy_hold": {},
    "ma_cross": {"fast": 20, "slow": 60},
    "momentum": {"lookback": 20},
}

STRATEGIES: Dict[str, StrategyFn] = {
    "buy_hold": buy_hold,
    "ma_cross": ma_cross,
    "momentum": momentum,
}


def get_strategy(name: str) -> StrategyFn:
    if name not in STRATEGIES:
        raise ValueError(f"未知策略: {name}，可选 {sorted(STRATEGIES)}")
    return STRATEGIES[name]
