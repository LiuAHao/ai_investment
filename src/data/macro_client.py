#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
宏观与指数环境数据客户端

宏观指标统一返回"最近若干期 + 可引用的数值"，不依赖精确列名（tushare 接口列名随版本变化）。
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

FIELD_LABELS = {
    "nt_val": "当月值",
    "nt_yoy": "同比",
    "nt_mom": "环比",
    "pmi010000": "制造业PMI",
    "pmi020000": "非制造业PMI",
    "pmi030000": "综合PMI",
    "on": "隔夜",
    "1w": "1周",
    "2w": "2周",
    "1m": "1月",
    "3m": "3月",
    "6m": "6月",
    "1y": "1年",
    "5y": "5年",
    "LPR1Y": "1年期",
    "m0_yoy": "M0 同比",
    "m1_yoy": "M1 同比",
    "m2_yoy": "M2 同比",
    "LPR5Y": "5年期",
    "rate_1y": "1年期",
    "rate_5y": "5年期",
}

MAIN_INDEXES = {
    "000001.SH": "上证指数",
    "399001.SZ": "深证成指",
    "399006.SZ": "创业板指",
    "000300.SH": "沪深300",
}


def get_macro_indicators(months: int = 12, as_of: Optional[str] = None) -> Dict[str, Any]:
    """PMI / CPI / Shibor / LPR"""
    evidence: List[Dict[str, Any]] = []
    sources: List[str] = []
    client = _client()
    if client is None:
        return {"source": "none", "evidence": [], "error": "tushare 不可用"}

    end = (as_of or datetime.now().strftime("%Y-%m-%d"))[:7].replace("-", "")
    start = _shift_month(end, -months)

    for name, call in (
        ("PMI", lambda: client.cn_pmi(start_m=start, end_m=end, fields="month,pmi010000")),
        ("M2", lambda: client.cn_m(start_m=start, end_m=end, fields="month,m1_yoy,m2_yoy")),
        ("CPI", lambda: client.cn_cpi(start_m=start, end_m=end)),
        ("Shibor", lambda: client.shibor(start_date=_to_date(start), end_date=_to_date(end))),
    ):
        try:
            df = call()
            if df is None or df.empty:
                continue
            df = df.sort_values(df.columns[0]).tail(2)
            latest = df.iloc[-1]
            rows = _numeric_fields(latest)
            if not rows:
                continue
            sources.append(name)
            pairs = [_fmt_field(key, value) for key, value in rows[:3]]
            evidence.append({
                "category": "macro",
                "statement": f"{name} {_period_label(latest)}：{'，'.join(pairs)}",
                "value": rows[0][1] if rows else None,
                "unit": "",
                "caliber": f"{name}/最新一期",
                "source_tool": "macro_indicator",
                "source_time": _period_label(latest),
                "confidence": 0.85,
            })
        except Exception as exc:  # noqa: BLE001
            logger.info("宏观指标 %s 不可用: %s", name, str(exc)[:100])

    try:
        lpr = client.lpr(start_date=_to_date(start), end_date=_to_date(end))
        if lpr is not None and not lpr.empty:
            latest = lpr.sort_values(lpr.columns[0]).iloc[-1]
            rows = _numeric_fields(latest)
            sources.append("LPR")
            pairs = [_fmt_field(key, value) for key, value in rows[:2]]
            evidence.append({
                "category": "policy",
                "statement": f"LPR {_period_label(latest)}：{'，'.join(pairs)}",
                "value": rows[0][1] if rows else None,
                "unit": "%",
                "caliber": "LPR/贷款市场报价利率",
                "source_tool": "macro_indicator",
                "source_time": _period_label(latest),
                "confidence": 0.9,
            })
    except Exception as exc:  # noqa: BLE001
        logger.info("LPR 不可用: %s", str(exc)[:100])

    try:
        fx = client.fx_daily(
            ts_code="USDCNH.FXCM",
            start_date=_to_date(start),
            end_date=_to_date(end),
        )
        if fx is not None and not fx.empty:
            latest = fx.sort_values("trade_date").iloc[-1]
            close = _to_float(latest.get("close")) or _to_float(latest.get("bid_close"))
            if close is not None:
                sources.append("USDCNH")
                evidence.append({
                    "category": "macro",
                    "statement": f"美元兑离岸人民币 {close:.4f}",
                    "value": round(close, 4),
                    "unit": "",
                    "caliber": "USDCNH/日收盘",
                    "source_tool": "macro_indicator",
                    "source_time": str(latest.get("trade_date") or ""),
                    "confidence": 0.8,
                })
    except Exception as exc:  # noqa: BLE001
        logger.info("汇率不可用: %s", str(exc)[:100])

    return {
        "source": ",".join(sources) if sources else "none",
        "evidence": evidence,
        "summary": f"宏观指标：{', '.join(sources) if sources else '不可用'}",
    }


def get_index_environment(as_of: Optional[str] = None) -> Dict[str, Any]:
    """主要指数点位、近 20/60 日涨跌幅、成交额"""
    client = _client()
    if client is None:
        return {"source": "none", "evidence": [], "error": "tushare 不可用"}

    end = (as_of or datetime.now().strftime("%Y-%m-%d")).replace("-", "")[:8]
    start = (datetime.strptime(end, "%Y%m%d") - timedelta(days=120)).strftime("%Y%m%d")
    evidence: List[Dict[str, Any]] = []
    rows: List[Dict[str, Any]] = []

    for ts_code, label in MAIN_INDEXES.items():
        try:
            df = client.index_daily(ts_code=ts_code, start_date=start, end_date=end)
            if df is None or df.empty:
                continue
            df = df.sort_values("trade_date").reset_index(drop=True)
            latest = float(df.iloc[-1]["close"])
            ret_20 = _pct_change(df, latest_idx=-1, offset=20)
            ret_60 = _pct_change(df, latest_idx=-1, offset=60)
            amount = _to_float(df.iloc[-1].get("amount"))
            trade_date = str(df.iloc[-1].get("trade_date") or "")
            evidence.append({
                "category": "market",
                "statement": f"{label} 收于 {latest:.2f}，近 20 日 {ret_20:+.1f}%，近 60 日 {ret_60:+.1f}%",
                "value": round(latest, 2),
                "unit": "点",
                "caliber": "指数收盘/前复权",
                "source_tool": "index_environment",
                "source_time": _fmt_date(trade_date),
                "confidence": 0.9,
            })
            rows.append({
                "index": label, "close": latest,
                "return_20d": ret_20, "return_60d": ret_60,
                "amount": amount, "date": trade_date,
            })
        except Exception as exc:  # noqa: BLE001
            logger.info("指数 %s 不可用: %s", label, str(exc)[:80])

    return {
        "source": "tushare",
        "evidence": evidence,
        "indexes": rows,
        "summary": f"指数环境：{len(rows)} 个指数",
    }


def _client():
    from data.tushare_client import get_client
    return get_client()


def _shift_month(month: str, delta: int) -> str:
    try:
        year, mon = int(month[:4]), int(month[4:6])
        total = year * 12 + (mon - 1) + delta
        return f"{total // 12}{total % 12 + 1:02d}"
    except (ValueError, IndexError):
        return month


def _to_date(month: str) -> str:
    return f"{month}01" if len(month) == 6 else month


def _period_label(row: pd.Series) -> str:
    for key in ("month", "date", "trade_date", "end_date"):
        if key in row.index and row.get(key) is not None:
            text = str(row.get(key))
            if len(text) == 6 and text.isdigit():
                return f"{text[:4]}-{text[4:]}"
            if len(text) == 8 and text.isdigit():
                return f"{text[:4]}-{text[4:6]}-{text[6:]}"
            return text[:10]
    return ""


RATE_FIELDS = {"on", "1w", "2w", "1m", "3m", "6m", "1y", "5y", "LPR1Y", "LPR5Y", "rate_1y", "rate_5y"}


def _fmt_field(key: str, value: float) -> str:
    """按字段语义格式化：同比/环比带正负号，利率带 %，指数值原样"""
    label = FIELD_LABELS.get(key, key)
    number = float(value)
    if key in ("nt_yoy", "nt_mom", "m1_yoy", "m2_yoy", "m0_yoy"):
        return f"{label} {number:+.1f}%"
    if key in RATE_FIELDS:
        return f"{label} {number:.2f}%"
    if number.is_integer():
        return f"{label} {number:.0f}"
    return f"{label} {number:g}"


def _numeric_fields(row: pd.Series) -> List[tuple]:
    values = []
    for key, value in row.items():
        if key in ("month", "date", "trade_date", "end_date"):
            continue
        number = _to_float(value)
        if number is not None:
            values.append((str(key), round(number, 4)))
    return values


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", "").replace("%", ""))
    except ValueError:
        return None


def _pct_change(df: pd.DataFrame, latest_idx: int, offset: int) -> float:
    if len(df) <= offset:
        return 0.0
    latest = _to_float(df.iloc[latest_idx].get("close")) or 0.0
    base = _to_float(df.iloc[latest_idx - offset].get("close")) or 0.0
    if not base:
        return 0.0
    return (latest / base - 1) * 100


def _fmt_date(value: str) -> str:
    text = str(value or "")
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return text[:10]
