#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
历史成分股（防幸存者偏差）

用 tushare index_weight 取决策时点的指数成分；取不到时明确标记 universe_bias。
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def historical_universe(
    index_code: str = "000300.SH",
    as_of: Optional[str] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    """
    Returns:
        {codes, index, as_of, universe_bias, error?}
        universe_bias=True 表示没拿到历史成分，样本不得进入统计汇总。
    """
    end = as_of or datetime.now().strftime("%Y-%m-%d")
    try:
        start_dt = datetime.strptime(end[:10], "%Y-%m-%d") - timedelta(days=45)
    except ValueError:
        start_dt = datetime.now() - timedelta(days=45)

    try:
        from data.tushare_client import get_client

        client = get_client()
        if client is None:
            return _fallback(end, "tushare 不可用")
        df = client.index_weight(
            index_code=index_code,
            start_date=start_dt.strftime("%Y%m%d"),
            end_date=end.replace("-", "")[:8],
        )
        if df is None or df.empty:
            return _fallback(end, "index_weight 无数据")
        date_col = "trade_date" if "trade_date" in df.columns else df.columns[0]
        latest_date = str(df[date_col].max())
        latest = df[df[date_col].astype(str) == latest_date]
        codes = [str(c) for c in latest.get("con_code", []) if c]
        if not codes:
            return _fallback(end, "成分股为空")
        return {
            "codes": codes[:limit],
            "index": index_code,
            "as_of": _fmt(latest_date),
            "universe_bias": False,
            "total": len(codes),
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("历史成分股获取失败: %s", exc)
        return _fallback(end, str(exc)[:120])


def _fallback(as_of: str, reason: str) -> Dict[str, Any]:
    return {
        "codes": [],
        "index": "",
        "as_of": as_of,
        "universe_bias": True,
        "error": reason,
        "total": 0,
    }


def _fmt(value: str) -> str:
    text = str(value)
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return text[:10]


def prepare_universe(
    index_code: str = "000300.SH",
    as_of: Optional[str] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    """回测启动时准备资产池；取不到历史成分则返回 universe_bias=True"""
    return historical_universe(index_code=index_code, as_of=as_of, limit=limit)
