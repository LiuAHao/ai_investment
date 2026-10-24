#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
扩展数据客户端（全部基于 tushare）

覆盖：
- 资金行为：moneyflow / margin_detail / top_list / moneyflow_hsgt / stk_holdernumber
- 预期与事件：forecast / express / disclosure_date
- 估值分位：daily_basic 历史
- 公司事件：dividend / share_float
- 行业相对强弱：stock_basic + daily + daily_basic 自算
- 港股日线：hk_daily

所有函数返回 {evidence: [...]}，失败时返回 {error}。
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd

from data.tushare_client import (
    _normalize_date,
    _normalize_symbol,
    _ts_code,
    get_client,
    get_hk_daily,
    get_trade_calendar,
)

logger = logging.getLogger(__name__)

_CACHE: Dict[tuple, tuple] = {}
_CACHE_TTL = 1800


# ==================== 通用工具 ====================

def _today(as_of: Optional[str]) -> str:
    return _normalize_date(as_of) or datetime.now().strftime("%Y%m%d")


def _shift(end: str, days: int) -> str:
    return (datetime.strptime(end, "%Y%m%d") - timedelta(days=days)).strftime("%Y%m%d")


def _num(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(number):
        return None
    return number


def _pick(row: Any, *names: str) -> Any:
    for name in names:
        try:
            value = row.get(name)
        except AttributeError:
            value = None
        if value is not None and not (isinstance(value, float) and pd.isna(value)):
            return value
    return None


def _evidence(
    statement: str,
    category: str,
    value: Optional[float] = None,
    unit: str = "",
    caliber: str = "",
    source_time: str = "",
    confidence: float = 0.8,
) -> Dict[str, Any]:
    return {
        "category": category,
        "statement": statement,
        "value": value,
        "unit": unit,
        "caliber": caliber,
        "source_time": source_time,
        "confidence": confidence,
    }


def _fmt_yi(amount_yuan: Optional[float]) -> str:
    if amount_yuan is None:
        return "—"
    return f"{amount_yuan / 1e8:.2f} 亿元"


def _percentile(values: Iterable[Any], current: Optional[float]) -> Optional[float]:
    """当前值在历史序列中的分位（0-100）"""
    clean = [v for v in (_num(item) for item in values) if v is not None]
    clean.sort()
    if not clean or current is None:
        return None
    below = sum(1 for v in clean if v <= current)
    return round(below / len(clean) * 100, 1)


def _recent_trade_date(end: str, back: int = 0) -> str:
    """返回 end 当天或之前的第 back 个交易日"""
    cal = get_trade_calendar(start_date=_shift(end, 60), end_date=end)
    if cal is None or cal.empty:
        return end
    dates = [str(d) for d in cal["cal_date"].tolist() if str(d) <= end]
    if not dates:
        return end
    index = max(0, len(dates) - 1 - max(0, back))
    return dates[index]


def _pit_filter(df: pd.DataFrame, as_of: Optional[str], date_col: str = "ann_date"):
    """回测：丢弃公告日晚于决策时点的记录（空公告日保留）"""
    if df is None or df.empty or not as_of:
        return df
    ref = _normalize_date(as_of)
    if not ref or date_col not in df.columns:
        return df
    values = df[date_col].astype(str).str.replace("-", "", regex=False)
    keep = (values <= ref) | values.isin(["", "nan", "None", "NaT"])
    return df[keep]

def _cached(key: tuple, builder):
    cached = _CACHE.get(key)
    if cached and time.time() - cached[0] < _CACHE_TTL:
        return cached[1]
    value = builder()
    _CACHE[key] = (time.time(), value)
    return value


# ==================== 资金行为 ====================

def get_fund_flow(symbol: str, days: int = 30, as_of: Optional[str] = None) -> Dict[str, Any]:
    client = get_client()
    code = _normalize_symbol(symbol)
    ts_code = _ts_code(code, "stock")
    if client is None or not ts_code:
        return {"symbol": symbol, "evidence": [], "error": "tushare 不可用或代码无法识别"}

    end = _today(as_of)
    start = _shift(end, max(days * 3, 45))
    evidence: List[Dict[str, Any]] = []

    # 1. 主力资金流
    try:
        df = client.moneyflow(ts_code=ts_code, start_date=start, end_date=end)
        if df is not None and not df.empty:
            df = df.sort_values("trade_date").tail(days)
            large_cols = ("buy_lg_amount", "buy_elg_amount", "sell_lg_amount", "sell_elg_amount")
            if all(col in df.columns for col in large_cols):
                net = (
                    pd.to_numeric(df["buy_lg_amount"], errors="coerce").fillna(0)
                    + pd.to_numeric(df["buy_elg_amount"], errors="coerce").fillna(0)
                    - pd.to_numeric(df["sell_lg_amount"], errors="coerce").fillna(0)
                    - pd.to_numeric(df["sell_elg_amount"], errors="coerce").fillna(0)
                ).sum()
                caliber = "大单+特大单净额"
            else:
                net = pd.to_numeric(df.get("net_mf_amount"), errors="coerce").fillna(0).sum()
                caliber = "全单净额"
            # moneyflow 金额单位为万元
            net_yuan = float(net) * 1e4
            latest_date = str(df["trade_date"].iloc[-1])
            sign = "净流入" if net_yuan >= 0 else "净流出"
            evidence.append(_evidence(
                f"近 {len(df)} 个交易日主力{sign} {abs(net_yuan) / 1e8:.2f} 亿元",
                "flow", round(net_yuan / 1e8, 2), "亿元", caliber, latest_date, 0.8,
            ))
    except Exception as exc:  # noqa: BLE001
        logger.info("moneyflow 不可用 %s: %s", ts_code, str(exc)[:100])

    # 2. 两融
    try:
        df = client.margin_detail(ts_code=ts_code, start_date=start, end_date=end)
        if df is not None and not df.empty:
            df = df.sort_values("trade_date")
            latest = df.iloc[-1]
            rzye = _num(_pick(latest, "rzye"))
            if rzye is not None:
                change = None
                if len(df) >= 6:
                    base = _num(_pick(df.iloc[-6], "rzye"))
                    if base:
                        change = (rzye - base) / base * 100
                suffix = f"，近 5 日变化 {change:+.1f}%" if change is not None else ""
                evidence.append(_evidence(
                    f"融资余额 {_fmt_yi(rzye)}{suffix}",
                    "flow", round(rzye / 1e8, 2), "亿元", "融资融券/融资余额",
                    str(_pick(latest, "trade_date") or ""), 0.85,
                ))
    except Exception as exc:  # noqa: BLE001
        logger.info("margin_detail 不可用 %s: %s", ts_code, str(exc)[:100])

    # 3. 北向资金（市场级）
    try:
        df = client.moneyflow_hsgt(start_date=start, end_date=end)
        if df is not None and not df.empty:
            df = df.sort_values("trade_date").tail(5)
            north = pd.to_numeric(df.get("north_money"), errors="coerce").fillna(0).sum()
            if abs(north) > 0:
                # tushare north_money 单位为万元
                evidence.append(_evidence(
                    f"北向资金近 {len(df)} 日净流入 {north / 1e4:.2f} 亿元",
                    "flow", round(north / 1e4, 2), "亿元", "北向资金/沪深港通",
                    str(df["trade_date"].iloc[-1]), 0.75,
                ))
    except Exception as exc:  # noqa: BLE001
        logger.info("moneyflow_hsgt 不可用: %s", str(exc)[:100])

    # 4. 股东户数
    try:
        df = client.stk_holdernumber(ts_code=ts_code, start_date=_shift(end, 730), end_date=end)
        if df is not None and not df.empty:
            df = df.sort_values("end_date")
            latest = df.iloc[-1]
            holders = _num(_pick(latest, "holder_num", "holder_nums"))
            if holders:
                change = None
                if len(df) >= 2:
                    prev = _num(_pick(df.iloc[-2], "holder_num", "holder_nums"))
                    if prev:
                        change = (holders - prev) / prev * 100
                suffix = f"，较上期 {change:+.1f}%" if change is not None else ""
                evidence.append(_evidence(
                    f"股东户数 {holders:.0f} 户{suffix}",
                    "flow", holders, "户", "股东户数/季度",
                    str(_pick(latest, "end_date") or ""), 0.7,
                ))
    except Exception as exc:  # noqa: BLE001
        logger.info("stk_holdernumber 不可用 %s: %s", ts_code, str(exc)[:100])

    return {"symbol": code, "evidence": evidence, "source": "tushare"}


# ==================== 预期与事件 ====================

def get_expectations(symbol: str, as_of: Optional[str] = None) -> Dict[str, Any]:
    client = get_client()
    code = _normalize_symbol(symbol)
    ts_code = _ts_code(code, "stock")
    if client is None or not ts_code:
        return {"symbol": symbol, "evidence": [], "error": "tushare 不可用或代码无法识别"}

    end = _today(as_of)
    start = _shift(end, 730)
    evidence: List[Dict[str, Any]] = []

    # 1. 业绩预告
    try:
        df = client.forecast(ts_code=ts_code, start_date=start, end_date=end)
        df = _pit_filter(df, as_of, "ann_date")
        if df is not None and not df.empty:
            df = df.drop_duplicates(subset=["end_date", "type"], keep="last")
            df = df.sort_values("ann_date").tail(2)
            for _, row in df.iterrows():
                kind = _pick(row, "type", "forecast_type") or "预告"
                low = _num(_pick(row, "p_change_min"))
                high = _num(_pick(row, "p_change_max"))
                period = str(_pick(row, "end_date") or "")
                ann = str(_pick(row, "ann_date") or "")
                if low is not None and high is not None:
                    text = f"{period} 业绩预告：{kind}，净利润变动 {low:+.1f}%~{high:+.1f}%（公告日 {ann}）"
                else:
                    text = f"{period} 业绩预告：{kind}（公告日 {ann}）"
                evidence.append(_evidence(text, "fundamental", high, "%", "业绩预告", ann, 0.85))
    except Exception as exc:  # noqa: BLE001
        logger.info("forecast 不可用 %s: %s", ts_code, str(exc)[:100])

    # 2. 业绩快报
    try:
        df = client.express(ts_code=ts_code, start_date=start, end_date=end)
        df = _pit_filter(df, as_of, "ann_date")
        if df is not None and not df.empty:
            row = df.sort_values("ann_date").iloc[-1]
            period = str(_pick(row, "end_date") or "")
            revenue = _num(_pick(row, "revenue"))
            profit = _num(_pick(row, "n_income"))
            yoy = _num(_pick(row, "yoy_net_profit"))
            parts = []
            if revenue is not None:
                parts.append(f"营收 {revenue / 1e8:.2f} 亿元")
            if profit is not None:
                parts.append(f"归母净利 {profit / 1e8:.2f} 亿元")
            if yoy is not None:
                parts.append(f"净利同比 {yoy:+.1f}%")
            if parts:
                evidence.append(_evidence(
                    f"{period} 业绩快报：{'，'.join(parts)}",
                    "fundamental", yoy, "%", "业绩快报",
                    str(_pick(row, "ann_date") or ""), 0.85,
                ))
    except Exception as exc:  # noqa: BLE001
        logger.info("express 不可用 %s: %s", ts_code, str(exc)[:100])

    # 3. 预约披露日
    try:
        df = client.disclosure_date(ts_code=ts_code, end_date=end)
        df = _pit_filter(df, as_of, "ann_date")
        if df is not None and not df.empty:
            row = df.iloc[-1]
            pre_date = _pick(row, "pre_date")
            period = _pick(row, "end_date")
            if pre_date:
                evidence.append(_evidence(
                    f"{period} 报告预约披露日 {pre_date}",
                    "fundamental", None, "", "预约披露", str(pre_date), 0.9,
                ))
    except Exception as exc:  # noqa: BLE001
        logger.info("disclosure_date 不可用 %s: %s", ts_code, str(exc)[:100])

    return {"symbol": code, "evidence": evidence, "source": "tushare"}


# ==================== 估值分位 ====================

def get_valuation_band(symbol: str, years: int = 5, as_of: Optional[str] = None) -> Dict[str, Any]:
    client = get_client()
    code = _normalize_symbol(symbol)
    ts_code = _ts_code(code, "stock")
    if client is None or not ts_code:
        return {"symbol": symbol, "evidence": [], "error": "tushare 不可用或代码无法识别"}

    end = _today(as_of)
    start = _shift(end, int(max(1, min(years, 10))) * 365)

    def build() -> Dict[str, Any]:
        evidence: List[Dict[str, Any]] = []
        try:
            df = client.daily_basic(
                ts_code=ts_code,
                start_date=start,
                end_date=end,
                fields="trade_date,pe_ttm,pb,ps_ttm,dv_ttm",
            )
        except Exception as exc:  # noqa: BLE001
            return {"symbol": code, "evidence": [], "error": str(exc)[:200]}
        if df is None or df.empty:
            return {"symbol": code, "evidence": [], "error": "daily_basic 未返回数据"}

        df = df.sort_values("trade_date")
        for field, label, positive_only in (
            ("pe_ttm", "PE(TTM)", True),
            ("pb", "PB", True),
            ("ps_ttm", "PS(TTM)", True),
            ("dv_ttm", "股息率", False),
        ):
            if field not in df.columns:
                continue
            series = pd.to_numeric(df[field], errors="coerce")
            series = series[series.notna()]
            if positive_only:
                series = series[series > 0]
            if series.empty:
                continue
            current = _num(series.iloc[-1])
            percentile = _percentile(series.tolist(), current)
            if current is None or percentile is None:
                continue
            value_text = f"{current:.2f}%" if field == "dv_ttm" else f"{current:.2f}"
            evidence.append(_evidence(
                f"{label} {value_text}，近 {years} 年分位 {percentile:.0f}%",
                "valuation", round(current, 2), "%" if field == "dv_ttm" else "倍",
                f"{label}/近{years}年分位", str(df["trade_date"].iloc[-1]), 0.85,
            ))
        return {"symbol": code, "evidence": evidence, "source": "tushare", "years": years}

    return _cached(("valuation", ts_code, years, end[:6]), build)


# ==================== 公司事件 ====================

def get_events(symbol: str, as_of: Optional[str] = None) -> Dict[str, Any]:
    client = get_client()
    code = _normalize_symbol(symbol)
    ts_code = _ts_code(code, "stock")
    if client is None or not ts_code:
        return {"symbol": symbol, "evidence": [], "error": "tushare 不可用或代码无法识别"}

    end = _today(as_of)
    evidence: List[Dict[str, Any]] = []

    # 1. 分红
    try:
        df = client.dividend(ts_code=ts_code)
        df = _pit_filter(df, as_of, "ann_date")
        if df is not None and not df.empty:
            df["div_proc"] = df["div_proc"].astype(str) if "div_proc" in df.columns else ""
            implemented = df[df["div_proc"].str.contains("实施")] if "div_proc" in df.columns else df
            pool = implemented if not implemented.empty else df
            pool = pool.drop_duplicates(subset=["end_date"], keep="last").sort_values("end_date").tail(2)
            picked = 0
            for _, row in reversed(list(pool.iterrows())):
                cash = _num(_pick(row, "cash_div_tax", "cash_div"))
                period = str(_pick(row, "end_date") or "")
                ex_date = _pick(row, "ex_date") or ""
                progress = _pick(row, "div_proc") or ""
                if cash is not None and cash > 0:
                    evidence.append(_evidence(
                        f"{period} 分红：每股派 {cash:.2f} 元（{progress}）",
                        "announcement", round(cash, 2), "元/股", "每股税前分红",
                        str(ex_date or _pick(row, "ann_date") or ""), 0.9,
                    ))
                    picked += 1
                    if picked >= 2:
                        break
    except Exception as exc:  # noqa: BLE001
        logger.info("dividend 不可用 %s: %s", ts_code, str(exc)[:100])

    # 2. 未来解禁
    try:
        df = client.share_float(ts_code=ts_code, start_date=end, end_date=_shift(end, -365))
        df = _pit_filter(df, as_of, "ann_date")
        if df is not None and not df.empty:
            df = df.sort_values("float_date").head(3)
            for _, row in df.iterrows():
                shares = _num(_pick(row, "float_share"))
                ratio = _num(_pick(row, "float_ratio"))
                if shares:
                    ratio_text = f"，占总股本 {ratio:.2f}%" if ratio is not None else ""
                    evidence.append(_evidence(
                        f"{_pick(row, 'float_date')} 解禁 {shares / 1e4:.2f} 亿股{ratio_text}",
                        "announcement", round(shares / 1e4, 2), "亿股", "限售解禁",
                        str(_pick(row, "float_date") or ""), 0.85,
                    ))
    except Exception as exc:  # noqa: BLE001
        logger.info("share_float 不可用 %s: %s", ts_code, str(exc)[:100])

    return {"symbol": code, "evidence": evidence, "source": "tushare"}


# ==================== 行业相对强弱 ====================

def get_industry_context(symbol: str, as_of: Optional[str] = None) -> Dict[str, Any]:
    client = get_client()
    code = _normalize_symbol(symbol)
    ts_code = _ts_code(code, "stock")
    if client is None or not ts_code:
        return {"symbol": symbol, "evidence": [], "error": "tushare 不可用或代码无法识别"}

    end = _today(as_of)

    def build() -> Dict[str, Any]:
        evidence: List[Dict[str, Any]] = []
        try:
            basic = client.stock_basic(ts_code=ts_code, fields="ts_code,name,industry")
            if basic is None or basic.empty:
                return {"symbol": code, "evidence": [], "error": "未找到行业信息"}
            industry = str(basic.iloc[0].get("industry") or "")
            all_basic = client.stock_basic(list_status="L", fields="ts_code,name,industry")
            peers = all_basic[all_basic["industry"] == industry]
            codes = set(peers["ts_code"].tolist())
            if not codes:
                return {"symbol": code, "evidence": [], "error": f"行业 {industry} 无成分股"}

            latest = ""
            now = None
            for back in range(0, 6):
                candidate = _recent_trade_date(end, back)
                frame_try = client.daily(trade_date=candidate, fields="ts_code,close,pct_chg")
                if frame_try is not None and not frame_try.empty:
                    latest, now = candidate, frame_try
                    break
            if now is None:
                return {"symbol": code, "evidence": [], "error": "daily 未返回数据（最近交易日无行情）"}
            past = _recent_trade_date(latest, 20)
            old = client.daily(trade_date=past, fields="ts_code,close")
            valuation = client.daily_basic(trade_date=latest, fields="ts_code,pe_ttm,pb")

            frame = now[now["ts_code"].isin(codes)].copy()
            if frame.empty:
                return {"symbol": code, "evidence": [], "error": "行业成分为空"}
            frame["pct_chg"] = pd.to_numeric(frame["pct_chg"], errors="coerce")
            target = frame[frame["ts_code"] == ts_code]
            avg_pct = frame["pct_chg"].mean()
            target_pct = _num(target.iloc[0]["pct_chg"]) if not target.empty else None
            rank = None
            if target_pct is not None:
                rank = int((frame["pct_chg"] > target_pct).sum()) + 1
            parts = [f"行业（{industry}，{len(frame)} 家）最近交易日等权涨幅 {avg_pct:+.2f}%"]
            if target_pct is not None:
                parts.append(f"目标股 {target_pct:+.2f}%，排名 {rank}/{len(frame)}")
            evidence.append(_evidence(
                "，".join(parts), "market", round(avg_pct, 2), "%", "行业等权/最近交易日",
                latest, 0.8,
            ))

            if old is not None and not old.empty:
                merged = frame.merge(
                    old[["ts_code", "close"]].rename(columns={"close": "close_old"}),
                    on="ts_code", how="left",
                )
                merged["close"] = pd.to_numeric(merged["close"], errors="coerce")
                merged["close_old"] = pd.to_numeric(merged["close_old"], errors="coerce")
                merged["ret20"] = (merged["close"] / merged["close_old"] - 1) * 100
                ret20_avg = merged["ret20"].mean()
                target_ret20 = merged.loc[merged["ts_code"] == ts_code, "ret20"]
                text = f"行业近 20 日等权涨幅 {ret20_avg:+.2f}%"
                if not target_ret20.empty and _num(target_ret20.iloc[0]) is not None:
                    text += f"，目标股 {_num(target_ret20.iloc[0]):+.2f}%"
                evidence.append(_evidence(
                    text, "market", round(ret20_avg, 2), "%", "行业等权/20 交易日",
                    latest, 0.8,
                ))

            if valuation is not None and not valuation.empty:
                vframe = valuation[valuation["ts_code"].isin(codes)].copy()
                vframe["pe_ttm"] = pd.to_numeric(vframe["pe_ttm"], errors="coerce")
                vframe = vframe[vframe["pe_ttm"] > 0]
                if not vframe.empty:
                    median_pe = vframe["pe_ttm"].median()
                    target_pe = vframe.loc[vframe["ts_code"] == ts_code, "pe_ttm"]
                    text = f"行业 PE(TTM) 中位数 {median_pe:.2f}"
                    if not target_pe.empty and _num(target_pe.iloc[0]) is not None:
                        text += f"，目标股 {_num(target_pe.iloc[0]):.2f}"
                    evidence.append(_evidence(
                        text, "valuation", round(float(median_pe), 2), "倍",
                        "行业中位/PE(TTM)", latest, 0.8,
                    ))
            return {"symbol": code, "industry": industry, "evidence": evidence, "source": "tushare"}
        except Exception as exc:  # noqa: BLE001
            logger.info("industry_context 失败 %s: %s", ts_code, str(exc)[:140])
            return {"symbol": code, "evidence": [], "error": str(exc)[:200]}

    return _cached(("industry", ts_code, end), build)


# ==================== 港股 ====================

def get_hk_history(symbol: str, days: int = 60, as_of: Optional[str] = None) -> Dict[str, Any]:
    code = _normalize_symbol(symbol) or symbol

    def build() -> Dict[str, Any]:
        return _get_hk_history_uncached(code, days, as_of)

    return _cached(("hk", code, days, _today(as_of)), build)


def _get_hk_history_uncached(symbol: str, days: int = 60, as_of: Optional[str] = None) -> Dict[str, Any]:
    end = _today(as_of)
    start = _shift(end, max(days * 2, 60))
    df = get_hk_daily(symbol, start_date=start, end_date=end, limit=max(days, 30))
    if df is None or df.empty:
        return {"symbol": symbol, "history": [], "error": "hk_daily 未返回数据（可能触发 1 次/分钟限频）"}
    df = df.sort_values("trade_date").tail(days)
    history = [
        {
            "date": str(_pick(row, "trade_date") or ""),
            "open": _num(_pick(row, "open")),
            "high": _num(_pick(row, "high")),
            "low": _num(_pick(row, "low")),
            "close": _num(_pick(row, "close")),
            "volume": _num(_pick(row, "vol")),
            "pct_chg": _num(_pick(row, "pct_chg")),
        }
        for _, row in df.iterrows()
    ]
    closes = [row["close"] for row in history if row["close"]]
    summary = {
        "rows": len(history),
        "latest_date": history[-1]["date"] if history else "",
        "latest_close": closes[-1] if closes else None,
        "total_return_pct": round((closes[-1] / closes[0] - 1) * 100, 2) if len(closes) > 1 else None,
    }
    return {"symbol": symbol, "history": history, "summary": summary, "source": "tushare"}
