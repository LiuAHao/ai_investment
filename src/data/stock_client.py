#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
数据 Agent：获取与分析行情数据
"""

from typing import Dict, Optional

import logging
import os
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta

import pandas as pd

logger = logging.getLogger(__name__)


# 历史行情进程内缓存：同一标的/区间/周期在 TTL 内只取一次，
# 避免一次工具调用内“日线分析 + 技术指标”重复抓取。
_HIST_CACHE: Dict[tuple, tuple] = {}
_HIST_CACHE_LOCK = threading.Lock()
_HIST_CACHE_TTL = int(os.getenv("HIST_CACHE_TTL_SECONDS", "120"))


def _cache_get(key: tuple):
    with _HIST_CACHE_LOCK:
        item = _HIST_CACHE.get(key)
        if not item:
            return None
        expires_at, df = item
        if time.time() > expires_at:
            _HIST_CACHE.pop(key, None)
            return None
        return df.copy()


def _cache_set(key: tuple, df) -> None:
    if df is None or len(df) == 0:
        return
    with _HIST_CACHE_LOCK:
        if len(_HIST_CACHE) > 256:
            _HIST_CACHE.clear()
        _HIST_CACHE[key] = (time.time() + _HIST_CACHE_TTL, df.copy())



class DataAgent:
    """数据 Agent"""

    @staticmethod
    @contextmanager
    def _without_proxy():
        if os.getenv("AKSHARE_DISABLE_PROXY", "0") != "1":
            yield
            return
        proxy_keys = [
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
            "http_proxy",
            "https_proxy",
            "all_proxy",
        ]
        backup = {key: os.environ.get(key) for key in proxy_keys if os.environ.get(key)}
        for key in proxy_keys:
            os.environ.pop(key, None)
        try:
            yield
        finally:
            for key, value in backup.items():
                os.environ[key] = value

    def __init__(self, default_start_date: Optional[str] = None, default_end_date: Optional[str] = None):
        from utils import pit

        as_of = pit.get_as_of()
        base = datetime.strptime(as_of, "%Y-%m-%d") if as_of else datetime.now()
        if default_end_date:
            self.default_end_date = default_end_date
        else:
            self.default_end_date = base.strftime("%Y%m%d")

        if default_start_date:
            self.default_start_date = default_start_date
        else:
            self.default_start_date = (base - timedelta(days=90)).strftime("%Y%m%d")

    def fetch_daily_hist(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        period: str = "daily",
        adjust: str = "",
        include_head: bool = True,
        kind: Optional[str] = None,
    ) -> Dict:
        """
        获取历史行情数据并返回摘要

        Args:
            symbol: 股票/指数/ETF 代码（支持带市场前缀，内部会处理）
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            period: 周期 ('daily', 'weekly', 'monthly')
            adjust: 复权类型 (""/"qfq"/"hfq")
            include_head: 是否包含前3行样例
            kind: 资产种类 (stock/index/etf/fund/hk)，None 则自动推断

        Returns:
            数据摘要字典
        """
        start = start_date or self.default_start_date
        end = end_date or self.default_end_date
        norm_symbol = self._normalize_symbol(symbol)
        logger.info(
            "数据Agent: 获取历史行情, symbol=%s, normalized=%s, start=%s, end=%s, period=%s, adjust=%s, kind=%s",
            symbol,
            norm_symbol,
            start,
            end,
            period,
            adjust,
            kind,
        )
        try:
            with self._without_proxy():
                df = self._fetch_hist_with_fallback(
                    symbol=norm_symbol,
                    start_date=start,
                    end_date=end,
                    period=period,
                    adjust=adjust,
                    kind=kind,
                )
        except Exception as exc:
            logger.error("数据Agent: 获取历史行情失败, error=%s", str(exc))
            return {"symbol": symbol, "rows": 0, "error": str(exc)}

        if df is None:
            return {"symbol": symbol, "rows": 0}

        summary = {
            "symbol": symbol,
            "rows": len(df),
            "columns": list(df.columns),
        }
        if include_head and len(df) > 0:
            summary["head"] = df.head(3).to_dict(orient="records")
        logger.info("数据Agent: 获取历史行情完成, rows=%s", len(df))
        return summary

    def _fetch_hist_with_fallback(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        period: str,
        adjust: str,
        kind: Optional[str] = None,
    ):
        """
        历史行情获取，按数据源降级回退。
        优先：tushare -> 东方财富 -> 新浪 -> 腾讯。
        指数/ETF 使用各自专用接口；所有兜底数据按请求区间截断。
        """
        key = (symbol, start_date, end_date, period, adjust, kind or "")
        cached = _cache_get(key)
        if cached is not None:
            logger.info("数据Agent: 历史行情命中缓存, symbol=%s", symbol)
            return cached

        def finalize(df):
            if df is None or len(df) == 0:
                return None
            sliced = self._slice_by_date(df, start_date, end_date)
            if sliced is None or len(sliced) == 0:
                return None
            _cache_set(key, sliced)
            return sliced

        freq_map = {"daily": "D", "weekly": "W", "monthly": "M"}
        # 1. tushare（token 认证，最稳定，支持 qfq/hfq 复权与周/月线）
        try:
            from data.tushare_client import get_daily
            ts_df = get_daily(
                symbol=symbol,
                start_date=start_date.replace("-", "") if start_date else None,
                end_date=end_date.replace("-", "") if end_date else None,
                adjust=adjust or "",
                freq=freq_map.get(period, "D"),
                limit=300,
                kind=kind,
            )
            finalized = finalize(self._rename_tushare_df(ts_df, adjust=adjust) if ts_df is not None else None)
            if finalized is not None:
                return finalized
        except Exception as exc:
            logger.warning("数据Agent: tushare 历史行情请求异常, error=%s", str(exc))

        logger.warning("数据Agent: tushare 未返回数据, symbol=%s, kind=%s", symbol, kind)
        return None

    @staticmethod
    def _slice_by_date(df, start_date, end_date):
        """按请求日期区间截断数据；日期列兼容 日期/date/trade_date。"""
        if df is None or len(df) == 0:
            return df
        date_col = next((col for col in ("日期", "date", "trade_date") if col in df.columns), None)
        if date_col is None:
            return df

        dates = pd.to_datetime(df[date_col], errors="coerce")
        mask = dates.notna()
        start = pd.to_datetime(str(start_date).replace("-", ""), format="%Y%m%d", errors="coerce")
        end = pd.to_datetime(str(end_date).replace("-", ""), format="%Y%m%d", errors="coerce")
        if pd.notna(start):
            mask &= dates >= start
        if pd.notna(end):
            mask &= dates <= end
        return df.loc[mask].reset_index(drop=True)

    @staticmethod
    def _rename_tushare_df(df, adjust: str = ""):
        """将 tushare 日线列名对齐为东方财富风格，并新增涨跌额/涨跌幅"""
        rename_map = {
            "trade_date": "日期", "open": "开盘", "high": "最高",
            "low": "最低", "close": "收盘", "pre_close": "昨收",
            "vol": "成交量", "amount": "成交额",
        }
        out = df.rename(columns=rename_map).copy()
        if "日期" in out.columns:
            out["日期"] = pd.to_datetime(out["日期"]).dt.strftime("%Y-%m-%d")
        if "涨跌额" not in out.columns and {"收盘", "昨收"}.issubset(out.columns):
            out["涨跌额"] = out["收盘"] - out["昨收"]
            out["涨跌幅"] = (out["涨跌额"] / out["昨收"].replace(0, pd.NA)) * 100
        if adjust:
            out.attrs["adjust"] = adjust
        return out

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        """
        统一股票代码格式为 6 位数字，兼容 SH/SZ/BJ 与 .SH/.SZ/.SS 后缀
        """
        if not symbol:
            return symbol
        value = str(symbol).strip().upper()
        if value.endswith((".SH", ".SZ", ".SS", ".BJ")):
            value = value.split(".")[0]
        if value.startswith(("SH", "SZ", "BJ")):
            value = value[2:]
        return value

    def analyze_daily_hist(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        period: str = "daily",
        adjust: str = "",
        kind: Optional[str] = None,
    ) -> Dict:
        """
        分析历史行情数据并输出关键指标

        Args:
            symbol: 股票/指数/ETF 代码
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            period: 周期 ('daily', 'weekly', 'monthly')
            adjust: 复权类型 (""/"qfq"/"hfq")
            kind: 资产种类 (stock/index/etf/fund/hk)，None 则自动推断

        Returns:
            分析结果字典
        """
        start = start_date or self.default_start_date
        end = end_date or self.default_end_date
        norm_symbol = self._normalize_symbol(symbol)
        logger.info(
            "数据Agent: 分析历史行情, symbol=%s, normalized=%s, start=%s, end=%s, period=%s, adjust=%s, kind=%s",
            symbol,
            norm_symbol,
            start,
            end,
            period,
            adjust,
            kind,
        )
        try:
            with self._without_proxy():
                df = self._fetch_hist_with_fallback(
                    symbol=norm_symbol,
                    start_date=start,
                    end_date=end,
                    period=period,
                    adjust=adjust,
                    kind=kind,
                )
        except Exception as exc:
            logger.error("数据Agent: 分析历史行情失败, error=%s", str(exc))
            return {"symbol": symbol, "rows": 0, "error": str(exc)}

        if df is None or len(df) == 0:
            logger.warning(
                "数据Agent: 分析历史行情为空, symbol=%s, normalized=%s, start=%s, end=%s, period=%s, adjust=%s",
                symbol,
                norm_symbol,
                start,
                end,
                period,
                adjust,
            )
            return {"symbol": symbol, "rows": 0}

        def pick_col(candidates):
            for col in candidates:
                if col in df.columns:
                    return col
            return None

        date_col = pick_col(["日期", "date"])
        close_col = pick_col(["收盘", "close"])
        open_col = pick_col(["开盘", "open"])
        high_col = pick_col(["最高", "high"])
        low_col = pick_col(["最低", "low"])
        pct_col = pick_col(["涨跌幅", "pct_change", "percent"])
        volume_col = pick_col(["成交量", "volume"])
        amount_col = pick_col(["成交额", "amount"])

        latest = df.iloc[-1]
        first = df.iloc[0]

        analysis: Dict[str, object] = {
            "symbol": symbol,
            "rows": len(df),
        }

        if date_col:
            analysis["start_date"] = str(first[date_col])
            analysis["end_date"] = str(latest[date_col])

        if close_col:
            analysis["latest_close"] = float(latest[close_col])
            analysis["first_close"] = float(first[close_col])
            if float(first[close_col]) != 0:
                analysis["total_return_pct"] = round(
                    (float(latest[close_col]) / float(first[close_col]) - 1) * 100,
                    4,
                )

        if open_col:
            analysis["latest_open"] = float(latest[open_col])

        if high_col:
            analysis["high_max"] = float(df[high_col].max())

        if low_col:
            analysis["low_min"] = float(df[low_col].min())

        if pct_col:
            try:
                analysis["latest_change_pct"] = float(latest[pct_col])
            except Exception:
                pass
        elif close_col:
            prev_close = df[close_col].iloc[-2] if len(df) > 1 else None
            if prev_close not in (None, 0):
                analysis["latest_change_pct"] = round(
                    (float(latest[close_col]) / float(prev_close) - 1) * 100,
                    4,
                )

        if close_col and len(df) > 1:
            returns = pd.Series(df[close_col]).pct_change().dropna()
            if len(returns) > 0:
                analysis["volatility_pct"] = round(float(returns.std() * 100), 4)

        if volume_col:
            analysis["avg_volume"] = float(pd.Series(df[volume_col]).mean())

        if amount_col:
            analysis["avg_amount"] = float(pd.Series(df[amount_col]).mean())
        logger.info("数据Agent: 分析历史行情完成, rows=%s", len(df))
        return analysis

    def analyze_technical_indicators(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        period: str = "daily",
        adjust: str = "",
        ma_windows: Optional[list] = None,
        kind: Optional[str] = None,
    ) -> Dict:
        """
        计算基础技术指标（MA/趋势/动量）
        Args:
            symbol: 股票/指数/ETF 代码
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            period: 周期 ('daily', 'weekly', 'monthly')
            adjust: 复权类型 (""/"qfq"/"hfq")
            ma_windows: 均线窗口列表
            kind: 资产种类 (stock/index/etf/fund/hk)，None 则自动推断

        Returns:
            技术指标摘要
        """
        start = start_date or self.default_start_date
        end = end_date or self.default_end_date
        norm_symbol = self._normalize_symbol(symbol)
        logger.info(
            "数据Agent: 计算技术指标, symbol=%s, normalized=%s, start=%s, end=%s, period=%s, adjust=%s, kind=%s",
            symbol,
            norm_symbol,
            start,
            end,
            period,
            adjust,
            kind,
        )

        try:
            with self._without_proxy():
                df = self._fetch_hist_with_fallback(
                    symbol=norm_symbol,
                    start_date=start,
                    end_date=end,
                    period=period,
                    adjust=adjust,
                    kind=kind,
                )
        except Exception as exc:
            logger.error("数据Agent: 技术指标失败, error=%s", str(exc))
            return {"symbol": symbol, "rows": 0, "error": str(exc)}

        if df is None or len(df) == 0:
            logger.warning(
                "数据Agent: 技术指标数据为空, symbol=%s, normalized=%s, start=%s, end=%s, period=%s, adjust=%s",
                symbol,
                norm_symbol,
                start,
                end,
                period,
                adjust,
            )
            return {"symbol": symbol, "rows": 0}

        def pick_col(candidates):
            for col in candidates:
                if col in df.columns:
                    return col
            return None

        close_col = pick_col(["收盘", "close"])
        if not close_col:
            return {"symbol": symbol, "rows": len(df), "error": "缺少收盘价字段"}

        if ma_windows is None:
            if len(df) >= 60:
                ma_windows = [5, 10, 20, 60]
            elif len(df) >= 20:
                ma_windows = [5, 10, 20]
            elif len(df) >= 10:
                ma_windows = [3, 5, 10]
            elif len(df) >= 6:
                ma_windows = [3, 5]
            elif len(df) >= 4:
                ma_windows = [2, 4]
            elif len(df) >= 3:
                ma_windows = [2, 3]
            else:
                ma_windows = [2]
        close_series = pd.Series(df[close_col])
        latest_close = float(close_series.iloc[-1])

        ma_values = {}
        for w in ma_windows:
            if len(close_series) >= w:
                ma_values[f"ma_{w}"] = round(float(close_series.rolling(w).mean().iloc[-1]), 4)

        trend = None
        if len(ma_values) >= 2:
            sorted_windows = sorted(ma_values.keys(), key=lambda k: int(k.split("_")[1]))
            short_key = sorted_windows[0]
            long_key = sorted_windows[-1]
            if ma_values[short_key] > ma_values[long_key]:
                trend = "上行"
            elif ma_values[short_key] < ma_values[long_key]:
                trend = "下行"
            else:
                trend = "横盘"

        momentum_pct = None
        if len(close_series) >= 2 and close_series.iloc[-2] != 0:
            momentum_pct = round((latest_close / float(close_series.iloc[-2]) - 1) * 100, 4)

        result = {
            "symbol": symbol,
            "rows": len(df),
            "latest_close": latest_close,
            "ma": ma_values,
            "trend": trend,
            "momentum_pct": momentum_pct,
        }
        logger.info("数据Agent: 技术指标完成, rows=%s", len(df))
        return result

    def summarize(self, symbol: str, kind: Optional[str] = None) -> Dict:
        """
        汇总股票基础信息与技术指标

        Args:
            symbol: 股票/指数/ETF 代码
            kind: 资产种类 (stock/index/etf/fund/hk)，None 则自动推断

        Returns:
            汇总字典
        """
        logger.info("数据Agent: 汇总开始, symbol=%s", symbol)
        analysis = self.analyze_daily_hist(symbol=symbol, kind=kind)
        technical = self.analyze_technical_indicators(symbol=symbol, kind=kind)
        valuation = self.fetch_valuation(symbol=symbol, kind=kind)
        return {
            "symbol": symbol,
            "analysis": analysis,
            "technical": technical,
            "valuation": valuation,
        }

    def fetch_valuation(self, symbol: str, kind: Optional[str] = None) -> Dict:
        """
        获取最新估值指标（PE/PB/市值等，tushare daily_basic / index_dailybasic）

        Args:
            symbol: 股票/指数代码
            kind: 资产种类 (stock/index)，None 则自动推断

        Returns:
            最新估值字典（空字典表示无数据）
        """
        try:
            from data.tushare_client import get_daily_basic, get_index_daily_basic
            from utils import pit

            code = self._normalize_symbol(symbol)
            as_of = pit.get_as_of()
            if kind == "index":
                df = get_index_daily_basic(code, end_date=as_of, limit=1)
            else:
                df = get_daily_basic(code, end_date=as_of, limit=1)
            if df is None or len(df) == 0:
                return {}
            row = df.iloc[-1]
            mapping = {
                "pe": "PE",
                "pe_ttm": "PE_TTM",
                "pb": "PB",
                "ps_ttm": "PS_TTM",
                "dv_ttm": "股息率(%)",
                "turnover_rate": "换手率(%)",
                "total_mv": "总市值(万)",
                "circ_mv": "流通市值(万)",
            }
            out: Dict[str, object] = {}
            if "trade_date" in df.columns:
                out["日期"] = str(row.get("trade_date", ""))
            for key, label in mapping.items():
                if key in df.columns and pd.notna(row.get(key)):
                    try:
                        out[label] = round(float(row[key]), 4)
                    except (TypeError, ValueError):
                        pass
            return out
        except Exception as exc:
            logger.warning("数据Agent: 获取估值失败 symbol=%s, error=%s", symbol, str(exc)[:120])
            return {}
