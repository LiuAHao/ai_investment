#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
量化回测数据层

- 日线，前复权（qfq）
- 复用项目 DataAgent（tushare），本地 CSV 缓存
- 统一输出列：date/open/high/low/close/volume/amount
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

import pandas as pd

CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "quant_cache"


def _cache_path(symbol: str, start: str, end: str, adjust: str) -> Path:
    safe = re.sub(r"[^0-9A-Za-z._-]", "_", str(symbol))
    name = f"{safe}_{start}_{end}_{adjust or 'none'}.csv"
    return CACHE_DIR / name


def load_prices(
    symbol: str,
    start: str,
    end: str,
    adjust: str = "qfq",
    use_cache: bool = True,
    kind: str | None = None,
) -> pd.DataFrame:
    """
    加载日线行情。

    Returns:
        DataFrame，列 date(datetime64) / open / high / low / close / volume / amount
    """
    cache_file = _cache_path(symbol, start, end, adjust)
    if use_cache and cache_file.exists():
        try:
            df = pd.read_csv(cache_file, parse_dates=["date"])
            if not df.empty:
                return df
        except Exception:
            pass

    from data.tushare_client import get_daily

    # 注意：stock_client 的历史接口内部 limit=300，不能用于长区间回测
    frame = get_daily(
        symbol=symbol,
        start_date=str(start).replace("-", ""),
        end_date=end,
        adjust=adjust,
        freq="D",
        limit=5000,
        kind=kind,
    )
    if frame is None or len(frame) == 0:
        raise ValueError(f"未获取到行情数据: {symbol} {start}~{end}")

    # get_daily 已同时返回 trade_date 与 date，避免重命名后出现重复 date 列
    if "date" in frame.columns and "trade_date" in frame.columns:
        frame = frame.drop(columns=["trade_date"])
    elif "日期" in frame.columns and "date" in frame.columns:
        frame = frame.drop(columns=["日期"])
    df = frame.rename(columns={
        "日期": "date", "开盘": "open", "最高": "high", "最低": "low",
        "收盘": "close", "成交量": "volume", "成交额": "amount",
        "trade_date": "date", "vol": "volume",
    })
    df = df.loc[:, ~df.columns.duplicated()]
    keep = ["date", "open", "high", "low", "close", "volume"]
    if "amount" in df.columns:
        keep.append("amount")
    df = df[[col for col in keep if col in df.columns]].copy()
    df["date"] = pd.to_datetime(df["date"])
    for col in ("open", "high", "low", "close", "volume"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = (
        df.dropna(subset=["close", "open"])
        .sort_values("date")
        .drop_duplicates("date")
        .reset_index(drop=True)
    )
    if df.empty:
        raise ValueError(f"行情数据为空: {symbol}")

    if use_cache:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            df.to_csv(cache_file, index=False)
        except Exception:
            pass
    return df
