#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tushare 数据源封装（增强版）
统一行情取数入口，覆盖 A股股票 / 指数 / ETF / 场内·场外基金 / 港股 / 全球指数 / 估值指标 / 交易日历。

优先级：tushare（token 认证）> akshare 东方财富 > 腾讯 > 新浪
依赖环境变量 TUSHARE_TOKEN。

接口权限（按本项目 token 实测）：
- 可用: daily / pro_bar(复权·周月线) / index_daily / fund_daily / fund_basic
       / fund_nav / daily_basic / index_dailybasic / trade_cal / stock_basic
       / index_global / index_basic / hk_daily
- 无权限(保留 akshare 兜底): us_daily / news / stk_factor
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

_TOKEN: Optional[str] = None
_CLIENT = None
_INIT_FAILED_AT: Optional[float] = None  # 上次初始化失败时间（冷却重试）
_RETRY_COOLDOWN_SECONDS = 300  # 失败后 5 分钟内不重复初始化，超时后允许重试


# ==================== 客户端初始化 ====================

def get_token() -> Optional[str]:
    """获取 Tushare token（读取环境变量）"""
    global _TOKEN
    if _TOKEN is None:
        _TOKEN = os.environ.get("TUSHARE_TOKEN", "").strip()
    return _TOKEN or None


def get_client():
    """
    惰性初始化 tushare pro 客户端

    初始化失败后进入冷却窗口避免高频重试；冷却结束后允许重新初始化，
    避免"一次性失败后进程内永远禁用"的旧问题。
    """
    global _CLIENT, _INIT_FAILED_AT
    if _CLIENT is not None:
        return _CLIENT
    if _INIT_FAILED_AT and (time.time() - _INIT_FAILED_AT) < _RETRY_COOLDOWN_SECONDS:
        return None
    token = get_token()
    if not token or token == "your-tushare-token":
        logger.warning("TUSHARE_TOKEN 未配置，跳过 tushare 数据源")
        _INIT_FAILED_AT = time.time()
        return None
    try:
        import tushare as ts

        ts.set_token(token)
        _CLIENT = ts.pro_api()
        logger.info("tushare pro 客户端初始化成功")
        return _CLIENT
    except Exception as exc:
        logger.warning("tushare 初始化失败: %s", exc)
        _INIT_FAILED_AT = time.time()
        return None


def is_available() -> bool:
    """tushare 数据源是否可用"""
    return get_client() is not None


# ==================== 代码解析 ====================

def _normalize_symbol(symbol: str) -> Optional[str]:
    """统一为纯代码：6 位 A股/基金代码、5 位港股代码、字母美股代码"""
    if not symbol:
        return None
    value = str(symbol).strip().upper()
    if value.endswith((".SH", ".SZ", ".SS", ".BJ", ".HK", ".OF")):
        value = value.split(".")[0]
    if value.startswith(("SH", "SZ", "BJ", "HK")):
        value = value[2:]
    if value.isdigit() and len(value) in (5, 6):
        return value
    if value.isalpha():
        return value
    return None


def _infer_kind(symbol: str) -> str:
    """根据代码规则推断资产种类: stock / index / etf / fund / hk / us / unknown"""
    code = _normalize_symbol(symbol)
    if not code:
        return "unknown"
    if code.isalpha():
        return "us"
    if len(code) == 5:
        return "hk"
    if code.startswith(("5", "1")):
        return "etf"  # 沪 5xxxxx / 深 1xxxxx 场内基金与 ETF
    if code.startswith(("4", "8")):
        return "stock"  # 北交所股票
    return "stock"  # 6/0/3 开头：股票或指数（歧义由调用方 kind 或自动兜底解决）


def _ts_code(code: Optional[str], kind: str = "stock") -> Optional[str]:
    """纯代码 + 资产种类 → tushare ts_code"""
    if not code:
        return None
    if kind == "hk":
        return f"{code}.HK"
    if kind == "index":
        if code.startswith("399"):
            return f"{code}.SZ"
        return f"{code}.SH"  # 000xxx 上证/中证系指数
    if kind in ("etf", "fund"):
        # 场内：沪 5xxxxx / 深 15xxx·16xxx（ETF/LOF）；其余 6 位代码按场外基金 .OF
        if code.startswith("5"):
            return f"{code}.SH"
        if code.startswith(("15", "16")):
            return f"{code}.SZ"
        return f"{code}.OF"
    # 股票
    if code.startswith(("6", "9")):
        return f"{code}.SH"
    if code.startswith(("8", "4")):
        return f"{code}.BJ"
    return f"{code}.SZ"


def _kind_candidates(kind: Optional[str], code: str) -> List[str]:
    """确定取数尝试顺序（显式类型优先，否则按代码规则推断并自动兜底）"""
    if kind and kind != "unknown":
        return [kind]
    if code.startswith("399"):
        return ["index", "stock"]
    if code.startswith(("5", "1")):
        return ["etf", "fund", "stock"]
    if code.startswith("0"):
        return ["stock", "index"]  # 000xxx 可能是深市股票，也可能是上证/中证指数
    return ["stock"]


def _normalize_date(value: Optional[str]) -> Optional[str]:
    """YYYY-MM-DD → YYYYMMDD；空值返回 None"""
    if not value:
        return None
    return str(value).replace("-", "").strip()


# ==================== 通用历史行情 ====================

def get_daily(
    symbol: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    adjust: str = "",
    freq: str = "D",
    limit: int = 250,
    kind: Optional[str] = None,
) -> Optional[pd.DataFrame]:
    """
    获取历史行情（统一入口，自动分流股票/指数/ETF/基金/港股）

    Args:
        symbol: 代码（兼容 SH600519 / 600519 / 600519.SH / 510300.SH）
        start_date: 开始日期 YYYYMMDD 或 YYYY-MM-DD
        end_date: 结束日期 YYYYMMDD 或 YYYY-MM-DD
        adjust: 复权类型 ""（不复权）/"qfq"（前复权）/"hfq"（后复权）
        freq: 频率 "D"（日）/ "W"（周）/ "M"（月）
        limit: 最多返回 N 条（默认最近 N 个交易日）
        kind: 资产种类 stock/index/etf/fund/hk，None 则自动推断

    Returns:
        DataFrame（列: ts_code/trade_date/open/high/low/close/pre_close/vol/amount/pct_chg），
        失败或无数据返回 None
    """
    code = _normalize_symbol(symbol)
    if code is None:
        return None
    client = get_client()
    if client is None:
        return None
    start = _normalize_date(start_date)
    end = _normalize_date(end_date) or datetime.now().strftime("%Y%m%d")
    if not start:
        start = (datetime.now() - timedelta(days=int(limit * 1.7))).strftime("%Y%m%d")

    for k in _kind_candidates(kind, code):
        ts_code = _ts_code(code, k)
        if not ts_code:
            continue
        df = _fetch_by_kind(client, k, ts_code, start, end, adjust, freq)
        if df is not None and len(df) > 0:
            out = _finalize_df(df, limit)
            out.attrs["source"] = "tushare"
            out.attrs["kind"] = k
            return out
        logger.warning("tushare %s(%s) 无数据, start=%s, end=%s", k, ts_code, start, end)
    return None


def _fetch_by_kind(
    client,
    kind: str,
    ts_code: str,
    start_date: str,
    end_date: str,
    adjust: str,
    freq: str,
) -> Optional[pd.DataFrame]:
    """按资产种类调用对应 tushare 接口"""
    try:
        if kind == "index":
            if freq and freq != "D":
                df = _pro_bar(ts_code, adjust="", freq=freq, asset="I", start=start_date, end=end_date)
                if df is not None and len(df) > 0:
                    return df
            return client.index_daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
        if kind in ("etf", "fund"):
            df = _pro_bar(ts_code, adjust=adjust, freq=freq, asset="FD", start=start_date, end=end_date)
            if df is not None and len(df) > 0:
                return df
            return client.fund_daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
        if kind == "hk":
            return client.hk_daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
        # 股票：pro_bar 支持复权与周/月线，回退 daily
        df = _pro_bar(ts_code, adjust=adjust, freq=freq, asset="E", start=start_date, end=end_date)
        if df is not None and len(df) > 0:
            return df
        return client.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
    except Exception as exc:
        logger.warning("tushare %s 请求失败 %s: %s", kind, ts_code, str(exc)[:120])
        return None


def _pro_bar(
    ts_code: str, adjust: str, freq: str, asset: str, start: str, end: str
) -> Optional[pd.DataFrame]:
    """tushare 聚合行情接口 pro_bar（支持复权与周/月线）"""
    try:
        import tushare as ts

        return ts.pro_bar(
            ts_code=ts_code,
            adj=adjust or None,
            freq=freq or "D",
            asset=asset,
            start_date=start,
            end_date=end,
        )
    except Exception as exc:
        logger.warning("tushare pro_bar 失败 %s: %s", ts_code, str(exc)[:120])
        return None


def _finalize_df(df: Optional[pd.DataFrame], limit: int) -> Optional[pd.DataFrame]:
    """统一排序与列名，保留 trade_date/open/high/low/close/pre_close/vol/amount/pct_chg"""
    if df is None or df.empty:
        return df
    df = df.copy()
    if "trade_date" in df.columns:
        df = df.sort_values("trade_date").reset_index(drop=True)
        df["date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")
    return df.tail(limit).reset_index(drop=True)


# ==================== 实时行情 ====================

def get_spot_summary(
    symbols: Optional[list] = None, limit: int = 50
) -> Optional[Dict[str, Any]]:
    """
    获取 A股实时行情摘要（tushare daily 当日快照；非交易日自动回退最近交易日）

    Args:
        symbols: 可选股票代码列表
        limit: 返回条目数量

    Returns:
        摘要字典（列含 代码/日期/开盘/最高/最低/收盘/昨收/涨跌额/涨跌幅/成交量/成交额）
    """
    client = get_client()
    if client is None:
        return None
    try:
        df = _latest_daily_snapshot(client)
        if df is None or df.empty:
            return None
        rename_map = {
            "ts_code": "代码", "trade_date": "日期",
            "open": "开盘", "high": "最高", "low": "最低",
            "close": "收盘", "pre_close": "昨收", "change": "涨跌额",
            "pct_chg": "涨跌幅", "vol": "成交量", "amount": "成交额",
        }
        out = df.rename(columns=rename_map).copy()
        if symbols:
            codes = []
            for s in symbols:
                code = _normalize_symbol(s)
                tc = _ts_code(code, "stock")
                if tc:
                    codes.append(tc)
            if codes:
                out = out[out["代码"].isin(codes)]
        out = out.head(limit)
        return {
            "rows": len(out),
            "columns": list(out.columns),
            "data": out.to_dict(orient="records"),
            "source": "tushare",
        }
    except Exception as exc:
        logger.warning("tushare get_spot_summary 失败: %s", exc)
        return None


def _latest_daily_snapshot(client) -> Optional[pd.DataFrame]:
    """从今天起往前最多 7 天，取最近一个有数据的交易日快照"""
    for back in range(0, 7):
        day = (datetime.now() - timedelta(days=back)).strftime("%Y%m%d")
        try:
            df = client.daily(trade_date=day)
            if df is not None and not df.empty:
                return df
        except Exception as exc:
            logger.warning("tushare daily 快照失败 %s: %s", day, str(exc)[:100])
            return None
    return None


# ==================== 估值指标 ====================

def get_daily_basic(
    symbol: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 5,
) -> Optional[pd.DataFrame]:
    """
    股票每日估值指标（PE/PB/总市值/流通市值/换手率）

    Returns:
        DataFrame（列: ts_code/trade_date/pe/pe_ttm/pb/total_mv/circ_mv/turnover_rate 等）
    """
    code = _normalize_symbol(symbol)
    client = get_client()
    if client is None or code is None:
        return None
    start = _normalize_date(start_date)
    end = _normalize_date(end_date) or datetime.now().strftime("%Y%m%d")
    try:
        ts_code = _ts_code(code, "stock")
        df = client.daily_basic(ts_code=ts_code, start_date=start, end_date=end)
        if df is None or df.empty:
            return None
        out = _finalize_df(df, limit)
        out.attrs["source"] = "tushare"
        return out
    except Exception as exc:
        logger.warning("tushare daily_basic 失败 %s: %s", symbol, str(exc)[:120])
        return None


def get_index_daily_basic(
    symbol: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 5,
) -> Optional[pd.DataFrame]:
    """
    指数每日估值指标（PE/PB/市值）

    Returns:
        DataFrame（列: ts_code/trade_date/pe/pe_ttm/pb/total_mv/float_mv/turnover_rate 等）
    """
    code = _normalize_symbol(symbol)
    client = get_client()
    if client is None or code is None:
        return None
    start = _normalize_date(start_date)
    end = _normalize_date(end_date) or datetime.now().strftime("%Y%m%d")
    try:
        ts_code = _ts_code(code, "index")
        df = client.index_dailybasic(ts_code=ts_code, start_date=start, end_date=end)
        if df is None or df.empty:
            return None
        out = _finalize_df(df, limit)
        out.attrs["source"] = "tushare"
        return out
    except Exception as exc:
        logger.warning("tushare index_dailybasic 失败 %s: %s", symbol, str(exc)[:120])
        return None


# ==================== 基金 ====================

def get_fund_profile(fund_code: str) -> Optional[Dict[str, Any]]:
    """
    基金基本信息（fund_basic，覆盖场内 ETF 与场外基金）

    Returns:
        字典（名称/管理人/托管人/基金类型/成立日期/上市日期/业绩基准/费率等）
    """
    code = _normalize_symbol(fund_code)
    client = get_client()
    if client is None or code is None:
        return None
    try:
        ts_code = _ts_code(code, "fund")
        if not ts_code:
            return None
        df = client.fund_basic(ts_code=ts_code)
        if df is None or df.empty:
            df = client.fund_basic(market="E", status="L")
            if df is not None and not df.empty:
                df = df[df["ts_code"] == ts_code]
        if df is None or df.empty:
            return None
        row = df.iloc[0]
        return {
            "ts_code": row.get("ts_code"),
            "名称": row.get("name"),
            "管理人": row.get("management"),
            "托管人": row.get("custodian"),
            "基金类型": row.get("fund_type"),
            "投资类型": row.get("invest_type"),
            "成立日期": row.get("found_date"),
            "上市日期": row.get("list_date"),
            "业绩基准": row.get("benchmark"),
            "管理费率": row.get("m_fee"),
            "托管费率": row.get("c_fee"),
        }
    except Exception as exc:
        logger.warning("tushare fund_basic 失败 %s: %s", fund_code, str(exc)[:120])
        return None


def get_fund_nav(
    fund_code: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 30,
) -> Optional[pd.DataFrame]:
    """
    基金历史净值（fund_nav，单位净值/累计净值）

    Returns:
        DataFrame（列: ts_code/nav_date/unit_nav/accum_nav 等，按净值日期升序）
    """
    code = _normalize_symbol(fund_code)
    client = get_client()
    if client is None or code is None:
        return None
    start = _normalize_date(start_date)
    end = _normalize_date(end_date) or datetime.now().strftime("%Y%m%d")
    try:
        ts_code = _ts_code(code, "fund")
        if not ts_code:
            return None
        df = client.fund_nav(ts_code=ts_code, start_date=start, end_date=end)
        if df is None or df.empty:
            return None
        df = df.sort_values("nav_date").reset_index(drop=True)
        out = df.tail(limit).reset_index(drop=True)
        out.attrs["source"] = "tushare"
        return out
    except Exception as exc:
        logger.warning("tushare fund_nav 失败 %s: %s", fund_code, str(exc)[:120])
        return None


# ==================== 港股与全球指数 ====================

# 全球主要指数别名 → tushare index_global ts_code
GLOBAL_INDEX_ALIASES = {
    "HSI": "XIN9", "HANG": "XIN9", "恒生": "XIN9", "恒生指数": "XIN9", "恒指": "XIN9",
    "DJI": "DJI", "道指": "DJI", "道琼斯": "DJI", "道琼斯指数": "DJI",
    "IXIC": "IXIC", "纳指": "IXIC", "纳斯达克": "IXIC", "纳斯达克指数": "IXIC",
    "SPX": "SPX", "标普": "SPX", "标普500": "SPX", "标普500指数": "SPX",
    "N225": "N225", "日经": "N225", "日经225": "N225", "日经指数": "N225",
    "XIN9": "XIN9", "SP500": "SPX", "S&P": "SPX", "NASDAQ": "IXIC",
}


def get_index_global(
    symbol: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 250,
) -> Optional[pd.DataFrame]:
    """
    全球主要指数日线（index_global）：恒生/道指/纳指/标普500/日经225

    Returns:
        DataFrame（列: ts_code/trade_date/open/high/low/close/pre_close/pct_chg/vol/amount）
    """
    client = get_client()
    if client is None:
        return None
    key = str(symbol or "").strip().upper()
    ts_code = GLOBAL_INDEX_ALIASES.get(key, key)
    start = _normalize_date(start_date)
    end = _normalize_date(end_date) or datetime.now().strftime("%Y%m%d")
    try:
        df = client.index_global(ts_code=ts_code, start_date=start, end_date=end)
        if df is None or df.empty:
            return None
        df = df.sort_values("trade_date").reset_index(drop=True)
        # index_global 无 pre_close/pct_chg，用收盘价补算
        if "pre_close" not in df.columns:
            df["pre_close"] = df["close"].shift(1)
        if "pct_chg" not in df.columns:
            df["pct_chg"] = ((df["close"] / df["pre_close"] - 1) * 100).round(4)
        df["date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")
        out = df.tail(limit).reset_index(drop=True)
        out.attrs["source"] = "tushare"
        return out
    except Exception as exc:
        logger.warning("tushare index_global 失败 %s: %s", symbol, str(exc)[:120])
        return None


def get_hk_daily(
    symbol: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 250,
) -> Optional[pd.DataFrame]:
    """
    港股日线（hk_daily）

    Args:
        symbol: 港股代码（5 位数字，如 00700 / 700）

    Returns:
        DataFrame（列: ts_code/trade_date/open/high/low/close/pre_close/vol/amount/pct_chg）
    """
    code = _normalize_symbol(symbol)
    if code is None or len(code) != 5:
        return None
    client = get_client()
    if client is None:
        return None
    start = _normalize_date(start_date)
    end = _normalize_date(end_date) or datetime.now().strftime("%Y%m%d")
    try:
        ts_code = f"{code}.HK"
        df = client.hk_daily(ts_code=ts_code, start_date=start, end_date=end)
        if df is None or df.empty:
            return None
        out = _finalize_df(df, limit)
        out.attrs["source"] = "tushare"
        return out
    except Exception as exc:
        logger.warning("tushare hk_daily 失败 %s: %s", symbol, str(exc)[:120])
        return None


# ==================== 交易日历 ====================

def get_trade_calendar(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    exchange: str = "SSE",
    limit: int = 30,
) -> Optional[pd.DataFrame]:
    """
    交易日历（trade_cal），仅返回开市日

    Returns:
        DataFrame（列: exchange/cal_date/is_open 等）
    """
    client = get_client()
    if client is None:
        return None
    start = _normalize_date(start_date)
    end = _normalize_date(end_date) or datetime.now().strftime("%Y%m%d")
    if not start:
        start = (datetime.now() - timedelta(days=int(limit * 2))).strftime("%Y%m%d")
    try:
        df = client.trade_cal(exchange=exchange, start_date=start, end_date=end)
        if df is None or df.empty:
            return None
        df = df[df["is_open"] == 1].sort_values("cal_date").reset_index(drop=True)
        df.attrs["source"] = "tushare"
        return df
    except Exception as exc:
        logger.warning("tushare trade_cal 失败: %s", str(exc)[:120])
        return None
