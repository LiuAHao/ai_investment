#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
美股数据客户端（Alpaca Data API v2）

移植自 quant-backtest-us 的 scripts/data_source/data_source_alpaca.py：
- 日线：GET /v2/stocks/{symbol}/bars
- 鉴权：环境变量 ALPACA_API_KEY / ALPACA_API_SECRET（请求头 APCA-*）
- feed 默认 iex（免费档），可通过 ALPACA_FEED 覆盖
- 密钥只从环境变量读取，不写入日志或返回值
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://data.alpaca.markets/v2"
DEFAULT_FEED = "iex"
DEFAULT_ADJUSTMENT = "all"
CACHE_TTL_SECONDS = 300

_CACHE: Dict[tuple, tuple] = {}


def _base_url() -> str:
    # 注意：ALPACA_API_BASE_URL 是交易 API（paper-api），数据接口必须用 data.alpaca.markets
    return (os.getenv("ALPACA_DATA_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")


def _credentials() -> tuple[str, str]:
    from utils.llm_common import load_env_file

    load_env_file()
    return (
        (os.getenv("ALPACA_API_KEY") or "").strip(),
        (os.getenv("ALPACA_API_SECRET") or "").strip(),
    )


def is_available() -> bool:
    key, secret = _credentials()
    return bool(key and secret)


def _normalize_symbol(symbol: str) -> str:
    """BRK.B -> BRK.B（Alpaca 使用点号），去掉 .US/.O 等后缀"""
    text = str(symbol or "").strip().upper()
    for suffix in (".US", ".O", ".N", ".OQ"):
        if text.endswith(suffix):
            text = text[: -len(suffix)]
    return text


def get_daily_bars(
    symbol: str,
    days: int = 60,
    feed: Optional[str] = None,
    adjustment: str = DEFAULT_ADJUSTMENT,
    timeout: int = 20,
) -> Dict[str, Any]:
    """
    获取美股日线（Alpaca bars，默认前复权）。

    Returns:
        {symbol, history[], summary{rows, latest_close, latest_date, total_return_pct}, source}
        失败时返回 {symbol, history: [], error}
    """
    clean_symbol = _normalize_symbol(symbol)
    if not clean_symbol:
        return {"symbol": symbol, "history": [], "error": "标的代码为空"}

    key, secret = _credentials()
    if not (key and secret):
        return {
            "symbol": clean_symbol,
            "history": [],
            "error": "未配置 ALPACA_API_KEY / ALPACA_API_SECRET",
        }

    use_feed = (feed or os.getenv("ALPACA_FEED") or DEFAULT_FEED).lower()
    cache_key = (clean_symbol, int(days), use_feed, adjustment)
    cached = _CACHE.get(cache_key)
    if cached and time.time() - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=max(int(days) * 2, 30))
    params: Dict[str, Any] = {
        "timeframe": "1Day",
        "start": start.strftime("%Y-%m-%d"),
        "end": end.strftime("%Y-%m-%d"),
        "adjustment": adjustment,
        "feed": use_feed,
        "limit": 10000,
    }
    headers = {
        "APCA-API-KEY-ID": key,
        "APCA-API-SECRET-KEY": secret,
        "accept": "application/json",
    }
    url = f"{_base_url()}/stocks/{clean_symbol}/bars"

    rows: List[Dict[str, Any]] = []
    page_token: Optional[str] = None
    try:
        while True:
            if page_token:
                params["page_token"] = page_token
            else:
                params.pop("page_token", None)
            response = requests.get(url, params=params, headers=headers, timeout=timeout)
            if response.status_code == 401:
                return {"symbol": clean_symbol, "history": [], "error": "Alpaca 鉴权失败（检查 API Key/Secret）"}
            if response.status_code == 403:
                return {"symbol": clean_symbol, "history": [], "error": "Alpaca 无该数据权限（检查订阅/feed）"}
            response.raise_for_status()
            payload = response.json()
            rows.extend(payload.get("bars") or [])
            page_token = payload.get("next_page_token")
            if not page_token:
                break
    except Exception as exc:  # noqa: BLE001
        logger.warning("Alpaca bars 获取失败 %s: %s", clean_symbol, str(exc)[:160])
        return {"symbol": clean_symbol, "history": [], "error": str(exc)[:200]}

    history = [
        {
            "date": str(bar.get("t") or "")[:10],
            "open": bar.get("o"),
            "high": bar.get("h"),
            "low": bar.get("l"),
            "close": bar.get("c"),
            "volume": bar.get("v"),
            "vwap": bar.get("vw"),
            "trades": bar.get("n"),
        }
        for bar in rows
        if bar.get("c") is not None
    ]
    history = history[-max(1, int(days)):]
    if not history:
        return {"symbol": clean_symbol, "history": [], "error": "Alpaca 未返回日线数据"}

    first_close = float(history[0]["close"])
    last_close = float(history[-1]["close"])
    total_return = ((last_close - first_close) / first_close * 100.0) if first_close else 0.0

    result = {
        "symbol": clean_symbol,
        "history": history,
        "summary": {
            "rows": len(history),
            "latest_close": last_close,
            "latest_date": history[-1]["date"],
            "total_return_pct": round(total_return, 2),
        },
        "source": f"alpaca_{use_feed}_{adjustment}",
    }
    _CACHE[cache_key] = (time.time(), result)
    return result
