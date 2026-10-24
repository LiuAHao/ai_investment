#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
财务数据客户端

tushare 优先（income / fina_indicator / balancesheet / cashflow / daily_basic），
不可用时返回明确错误，不再降级第三方源。

PIT：所有数据按 ann_date（公告日）过滤，回测中不会拿到决策时点之后才披露的报表。
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

_AMOUNT_FIELDS = {
    "total_revenue": "营业总收入",
    "revenue": "营业收入",
    "n_income_attr_p": "归母净利润",
    "n_income": "净利润",
    "n_cashflow_act": "经营现金流净额",
    "total_assets": "总资产",
    "total_liab": "总负债",
}


def _client():
    from data.tushare_client import get_client
    return get_client()


def _ts_code(symbol: str) -> Optional[str]:
    from data.tushare_client import _normalize_symbol, _ts_code as build
    code = _normalize_symbol(symbol)
    if not code:
        return None
    return build(code, "stock")


def _compact(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return str(value).replace("-", "").strip()


def _filter_pit(df: pd.DataFrame, as_of: Optional[str]) -> pd.DataFrame:
    """按公告日过滤：只保留决策时点前已披露的报表"""
    if df is None or df.empty or not as_of:
        return df
    ref = _compact(as_of)
    if not ref or "ann_date" not in df.columns:
        return df
    ann = df["ann_date"].astype(str)
    return df[ann <= ref]


def _sort_periods(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    if "end_date" in df.columns:
        df = df.sort_values("end_date")
    if "report_type" in df.columns:
        # 只保留合并报表（report_type=1），没有该列则跳过
        merged = df[df["report_type"].astype(str) == "1"]
        if not merged.empty:
            df = merged
    if "end_date" in df.columns:
        df = df.drop_duplicates(subset=["end_date"], keep="last")
    return df.reset_index(drop=True)


def _num(row: pd.Series, key: str) -> Optional[float]:
    if key not in row.index:
        return None
    value = row.get(key)
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _yoy(series: pd.Series, offset: int = 4) -> Optional[float]:
    values = [v for v in series.tolist() if v is not None and not pd.isna(v)]
    if len(values) <= offset:
        return None
    latest = values[-1]
    base = values[-1 - offset]
    if not base:
        return None
    return (latest / base - 1) * 100


def get_financial_summary(symbol: str, periods: int = 8, as_of: Optional[str] = None) -> Dict[str, Any]:
    """
    财务摘要：营收/利润/现金流/资产负债 + 同比。

    Returns:
        {symbol, source, periods: [...], evidence: [...], error?}
    """
    code = _ts_code(symbol)
    if not code:
        return {"symbol": symbol, "error": "无法解析股票代码", "evidence": []}

    client = _client()
    if client is not None:
        try:
            end = _compact(as_of) or datetime.now().strftime("%Y%m%d")
            start = f"{int(end[:4]) - 3}0101"
            income = client.income(ts_code=code, start_date=start, end_date=end)
            balance = client.balancesheet(ts_code=code, start_date=start, end_date=end)
            cash = client.cashflow(ts_code=code, start_date=start, end_date=end)
            income = _sort_periods(_filter_pit(income, as_of))
            balance = _sort_periods(_filter_pit(balance, as_of))
            cash = _sort_periods(_filter_pit(cash, as_of))
            if income is not None and not income.empty:
                rows = income.tail(periods)
                revenue_series = rows["total_revenue"] if "total_revenue" in rows else rows.get("revenue")
                profit_series = rows["n_income_attr_p"] if "n_income_attr_p" in rows else rows.get("n_income")
                latest = rows.iloc[-1]
                latest_period = str(latest.get("end_date") or "")
                evidence: List[Dict[str, Any]] = []

                revenue = _num(latest, "total_revenue") or _num(latest, "revenue")
                if revenue is not None:
                    evidence.append(_evidence(
                        f"{latest_period} 营业总收入 {revenue / 1e8:.2f} 亿元",
                        revenue / 1e8, "亿元", "合并报表/累计", "total_revenue",
                        str(latest.get("ann_date") or ""),
                    ))
                revenue_yoy = _yoy(revenue_series) if revenue_series is not None else None
                if revenue_yoy is not None:
                    evidence.append(_evidence(
                        f"{latest_period} 营业总收入同比 {revenue_yoy:.1f}%",
                        round(revenue_yoy, 2), "%", "累计同比", "total_revenue",
                        str(latest.get("ann_date") or ""),
                    ))
                profit = _num(latest, "n_income_attr_p") or _num(latest, "n_income")
                if profit is not None:
                    evidence.append(_evidence(
                        f"{latest_period} 归母净利润 {profit / 1e8:.2f} 亿元",
                        profit / 1e8, "亿元", "合并报表/累计", "n_income_attr_p",
                        str(latest.get("ann_date") or ""),
                    ))
                profit_yoy = _yoy(profit_series) if profit_series is not None else None
                if profit_yoy is not None:
                    evidence.append(_evidence(
                        f"{latest_period} 归母净利润同比 {profit_yoy:.1f}%",
                        round(profit_yoy, 2), "%", "累计同比", "n_income_attr_p",
                        str(latest.get("ann_date") or ""),
                    ))
                if cash is not None and not cash.empty:
                    c_row = cash.iloc[-1]
                    ocf = _num(c_row, "n_cashflow_act")
                    if ocf is not None:
                        evidence.append(_evidence(
                            f"{c_row.get('end_date')} 经营活动现金流净额 {ocf / 1e8:.2f} 亿元",
                            round(ocf / 1e8, 2), "亿元", "合并报表/累计", "n_cashflow_act",
                            str(c_row.get("ann_date") or ""),
                        ))
                if balance is not None and not balance.empty:
                    b_row = balance.iloc[-1]
                    assets = _num(b_row, "total_assets")
                    liab = _num(b_row, "total_liab")
                    if assets and liab is not None:
                        ratio = liab / assets * 100
                        evidence.append(_evidence(
                            f"{b_row.get('end_date')} 资产负债率 {ratio:.1f}%",
                            round(ratio, 2), "%", "合并报表", "total_liab/total_assets",
                            str(b_row.get("ann_date") or ""),
                        ))
                    goodwill = _num(b_row, "goodwill")
                    if goodwill is not None and assets:
                        evidence.append(_evidence(
                            f"{b_row.get('end_date')} 商誉占总资产 {goodwill / assets * 100:.1f}%",
                            round(goodwill / assets * 100, 2), "%", "合并报表", "goodwill",
                            str(b_row.get("ann_date") or ""),
                        ))

                return {
                    "symbol": code,
                    "source": "tushare",
                    "latest_period": latest_period,
                    "evidence": evidence,
                    "periods": rows.to_dict(orient="records")[-periods:],
                }
        except Exception as exc:  # noqa: BLE001
            logger.warning("tushare 财务摘要失败 %s: %s", symbol, exc)
            return {"symbol": symbol, "source": "none", "error": str(exc), "evidence": []}

def get_financial_indicators(symbol: str, periods: int = 8, as_of: Optional[str] = None) -> Dict[str, Any]:
    """财务指标时序：ROE / 毛利率 / 净利率 / 负债率 / 周转率"""
    code = _ts_code(symbol)
    client = _client()
    if client is None or not code:
        return {"symbol": symbol, "error": "tushare 不可用", "evidence": []}
    try:
        end = _compact(as_of) or datetime.now().strftime("%Y%m%d")
        start = f"{int(end[:4]) - 3}0101"
        df = client.fina_indicator(ts_code=code, start_date=start, end_date=end)
        df = _sort_periods(_filter_pit(df, as_of))
        if df is None or df.empty:
            return {"symbol": code, "source": "tushare", "evidence": [], "error": "无数据"}
        rows = df.tail(periods)
        latest = rows.iloc[-1]
        period = str(latest.get("end_date") or "")
        ann = str(latest.get("ann_date") or "")
        evidence = []
        for key, label, unit in (
            ("roe", "ROE", "%"),
            ("grossprofit_margin", "毛利率", "%"),
            ("netprofit_margin", "净利率", "%"),
            ("debt_to_assets", "资产负债率", "%"),
            ("ar_turn", "应收账款周转率", "次"),
            ("inventory_turn", "存货周转率", "次"),
            ("current_ratio", "流动比率", ""),
        ):
            value = _num(latest, key)
            if value is not None:
                evidence.append(_evidence(
                    f"{period} {label} {value:.2f}{unit}",
                    round(value, 2), unit, "合并报表/报告期", key, ann,
                ))
        return {
            "symbol": code,
            "source": "tushare",
            "latest_period": period,
            "evidence": evidence,
            "periods": rows.to_dict(orient="records")[-periods:],
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("tushare 财务指标失败 %s: %s", symbol, exc)
        return {"symbol": symbol, "error": str(exc), "evidence": []}


def _daily_basic(client, start_date: str) -> Optional[pd.DataFrame]:
    """按交易日回退拉取 daily_basic（当天可能未更新）"""
    from datetime import timedelta

    try:
        day = datetime.strptime(start_date, "%Y%m%d")
    except ValueError:
        return None
    for _ in range(7):
        candidate = day.strftime("%Y%m%d")
        try:
            df = client.daily_basic(
                trade_date=candidate,
                fields="ts_code,pe_ttm,pb,close,pct_chg",
            )
        except Exception:
            df = None
        if df is not None and not df.empty:
            df.attrs["trade_date"] = candidate
            return df
        day -= timedelta(days=1)
    return None


def get_peer_compare(symbol: str, limit: int = 10, as_of: Optional[str] = None) -> Dict[str, Any]:
    """
    同业估值对比：取同行业公司 PE/PB/涨跌幅，计算目标公司的分位。
    """
    code = _ts_code(symbol)
    client = _client()
    if client is None or not code:
        return {"symbol": symbol, "error": "tushare 不可用", "evidence": []}
    try:
        basic = client.stock_basic(ts_code=code, fields="ts_code,name,industry")
        if basic is None or basic.empty:
            return {"symbol": symbol, "error": "未找到行业信息", "evidence": []}
        industry = str(basic.iloc[0].get("industry") or "")
        # stock_basic 不支持 industry 参数过滤，拉全市场后在本地筛选
        basic_all = client.stock_basic(list_status="L", fields="ts_code,name,industry")
        if basic_all is None or basic_all.empty:
            return {"symbol": symbol, "error": "未获取到股票基础信息", "evidence": []}
        peers = basic_all[basic_all["industry"] == industry]
        if peers.empty:
            return {"symbol": symbol, "error": f"行业 {industry} 无同行业数据", "evidence": []}
        codes = set(peers["ts_code"].tolist())
        start_date = _compact(as_of) or datetime.now().strftime("%Y%m%d")
        daily = _daily_basic(client, start_date)
        if daily is None or daily.empty:
            return {"symbol": code, "error": "无估值数据", "evidence": []}
        trade_date = daily.attrs.get("trade_date", start_date)
        daily = daily[daily["ts_code"].isin(codes)]
        target = daily[daily["ts_code"] == code]
        if target.empty:
            return {"symbol": code, "error": "目标公司无估值数据", "evidence": []}

        evidence: List[Dict[str, Any]] = []
        for key, label in (("pe_ttm", "PE(TTM)"), ("pb", "PB")):
            if key not in daily.columns:
                continue
            series = pd.to_numeric(daily[key], errors="coerce").dropna()
            if series.empty:
                continue
            raw_value = target.iloc[0].get(key)
            if raw_value is None or pd.isna(raw_value):
                continue
            value = float(raw_value)
            if not value:
                continue
            percentile = float((series <= value).mean() * 100)
            evidence.append(_evidence(
                f"同行业（{industry}，{len(series)} 家）{label} 分位 {percentile:.0f}%，目标公司 {value:.2f}",
                round(percentile, 1), "%", f"同业分位/{label}", key, trade_date,
            ))
        return {
            "symbol": code,
            "source": "tushare",
            "industry": industry,
            "peer_count": int(len(daily)),
            "evidence": evidence,
            "peers": daily.head(limit).to_dict(orient="records"),
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("同业对比失败 %s: %s", symbol, exc)
        return {"symbol": symbol, "error": str(exc), "evidence": []}


def _evidence(statement: str, value: Any, unit: str, caliber: str, tag: str, source_time: str) -> Dict[str, Any]:
    return {
        "category": "fundamental",
        "statement": statement,
        "value": value,
        "unit": unit,
        "caliber": caliber,
        "source_tool": "stock_financial_summary",
        "source_time": source_time,
        "confidence": 0.9 if source_time else 0.7,
    }
