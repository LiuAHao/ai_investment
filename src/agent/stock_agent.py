#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
股票 Agent：获取与分析行情数据
"""

from typing import Dict, Optional

import logging
import os
from contextlib import contextmanager
from datetime import datetime, timedelta

import pandas as pd

logger = logging.getLogger(__name__)

from stock.stock_api import (
    get_stock_sse_deal_daily,
    get_stock_sse_summary,
    get_stock_szse_summary,
    get_stock_zh_a_daily,
    get_stock_zh_a_hist,
    get_stock_zh_a_hist_tx,
    get_stock_zh_a_spot_em,
)


class StockAgent:
    """股票 Agent"""

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
        if default_end_date:
            self.default_end_date = default_end_date
        else:
            self.default_end_date = datetime.now().strftime("%Y%m%d")

        if default_start_date:
            self.default_start_date = default_start_date
        else:
            start = datetime.now() - timedelta(days=90)
            self.default_start_date = start.strftime("%Y%m%d")

    def fetch_daily_hist(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        period: str = "daily",
        adjust: str = "",
        include_head: bool = True,
    ) -> Dict:
        """
        获取历史行情数据并返回摘要

        Args:
            symbol: 股票代码（支持带提醒前缀，内部会处理）
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            period: 周期 ('daily', 'weekly', 'monthly')
            adjust: 复权类型 (""/"qfq"/"hfq")
            include_head: 是否包含前3行样例

        Returns:
            数据摘要字典
        """
        start = start_date or self.default_start_date
        end = end_date or self.default_end_date
        norm_symbol = self._normalize_symbol(symbol)
        logger.info(
            "股票Agent: 获取历史行情, symbol=%s, normalized=%s, start=%s, end=%s, period=%s, adjust=%s",
            symbol,
            norm_symbol,
            start,
            end,
            period,
            adjust,
        )
        try:
            with self._without_proxy():
                df = self._fetch_hist_with_fallback(
                    symbol=norm_symbol,
                    start_date=start,
                    end_date=end,
                    period=period,
                    adjust=adjust,
                )
        except Exception as exc:
            logger.error("股票Agent: 获取历史行情失败, error=%s", str(exc))
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
        logger.info("股票Agent: 获取历史行情完成, rows=%s", len(df))
        return summary

    def _fetch_hist_with_fallback(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        period: str,
        adjust: str,
    ):
        """
        历史行情获取，按数据源降级回退
        优先：东方财富 -> 腾讯 -> 新浪
        """
        try:
            df = get_stock_zh_a_hist(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                period=period,
                adjust=adjust,
            )
        except Exception as exc:
            logger.warning("股票Agent: 东方财富请求异常，进入回退流程, error=%s", str(exc))
            df = None
        if df is not None and len(df) > 0:
            return df

        logger.warning("股票Agent: 东方财富返回空数据，尝试腾讯历史数据")
        try:
            df = get_stock_zh_a_hist_tx(symbol=symbol, adjust=adjust)
        except Exception:
            df = None
        if df is not None and len(df) > 0:
            return df

        logger.warning("股票Agent: 腾讯返回空数据，尝试新浪日线数据")
        try:
            df = get_stock_zh_a_daily(symbol=symbol, adjust=adjust)
        except Exception:
            df = None
        return df

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

    def fetch_spot_em(self, symbols: Optional[list] = None, limit: int = 50) -> Dict:
        """
        获取沪深京 A 股实时行情摘要

        Args:
            symbols: 可选股票/指数代码或名称列表
            limit: 返回条目数量

        Returns:
            摘要字典
        """
        logger.info("股票Agent: 获取实时行情, symbols=%s, limit=%s", symbols, limit)
        try:
            with self._without_proxy():
                df = get_stock_zh_a_spot_em()
        except Exception as exc:
            logger.error("股票Agent: 获取实时行情失败, error=%s", str(exc))
            return {"rows": 0, "error": str(exc)}

        if df is None or len(df) == 0:
            return {"rows": 0}

        filtered = df
        if symbols:
            keywords = [str(s).strip() for s in symbols if str(s).strip()]
            if keywords:
                code_col = "代码" if "代码" in df.columns else None
                name_col = "名称" if "名称" in df.columns else None
                if code_col or name_col:
                    mask = False
                    for kw in keywords:
                        if code_col:
                            mask = mask | df[code_col].astype(str).str.contains(kw, na=False)
                        if name_col:
                            mask = mask | df[name_col].astype(str).str.contains(kw, na=False)
                    filtered = df[mask] if hasattr(mask, "any") else df

        data = filtered.head(limit).to_dict(orient="records")
        return {
            "rows": len(filtered),
            "columns": list(filtered.columns),
            "data": data,
        }

    def fetch_sse_summary(self) -> Dict:
        """
        获取上交所市场总貌

        Returns:
            汇总字典
        """
        logger.info("股票Agent: 获取上交所市场总貌")
        try:
            with self._without_proxy():
                df = get_stock_sse_summary()
        except Exception as exc:
            logger.error("股票Agent: 获取上交所总貌失败, error=%s", str(exc))
            return {"rows": 0, "error": str(exc)}

        if df is None or len(df) == 0:
            return {"rows": 0}
        return {
            "rows": len(df),
            "columns": list(df.columns),
            "data": df.to_dict(orient="records"),
        }

    def fetch_szse_summary(self, date: Optional[str] = None) -> Dict:
        """
        获取深交所市场总貌

        Args:
            date: 日期 YYYYMMDD

        Returns:
            汇总字典
        """
        use_date = date.replace("-", "") if date else ""
        logger.info("股票Agent: 获取深交所市场总貌, date=%s", use_date or "latest")
        try:
            with self._without_proxy():
                df = get_stock_szse_summary(date=use_date)
        except Exception as exc:
            logger.error("股票Agent: 获取深交所总貌失败, error=%s", str(exc))
            return {"rows": 0, "error": str(exc)}

        if df is None or len(df) == 0:
            return {"rows": 0}
        return {
            "rows": len(df),
            "columns": list(df.columns),
            "data": df.to_dict(orient="records"),
        }

    def fetch_sse_deal_daily(self, date: Optional[str] = None) -> Dict:
        """
        获取上交所每日概况

        Args:
            date: 日期 YYYYMMDD

        Returns:
            汇总字典
        """
        use_date = date.replace("-", "") if date else ""
        logger.info("股票Agent: 获取上交所每日概况, date=%s", use_date or "latest")
        try:
            with self._without_proxy():
                df = get_stock_sse_deal_daily(date=use_date)
        except Exception as exc:
            logger.error("股票Agent: 获取上交所每日概况失败, error=%s", str(exc))
            return {"rows": 0, "error": str(exc)}

        if df is None or len(df) == 0:
            return {"rows": 0}
        return {
            "rows": len(df),
            "columns": list(df.columns),
            "data": df.to_dict(orient="records"),
        }

    def analyze_daily_hist(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        period: str = "daily",
        adjust: str = "",
    ) -> Dict:
        """
        分析历史行情数据并输出关键指标

        Args:
            symbol: 股票代码
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            period: 周期 ('daily', 'weekly', 'monthly')
            adjust: 复权类型 (""/"qfq"/"hfq")

        Returns:
            分析结果字典
        """
        start = start_date or self.default_start_date
        end = end_date or self.default_end_date
        norm_symbol = self._normalize_symbol(symbol)
        logger.info(
            "股票Agent: 分析历史行情, symbol=%s, normalized=%s, start=%s, end=%s, period=%s, adjust=%s",
            symbol,
            norm_symbol,
            start,
            end,
            period,
            adjust,
        )
        try:
            with self._without_proxy():
                df = self._fetch_hist_with_fallback(
                    symbol=norm_symbol,
                    start_date=start,
                    end_date=end,
                    period=period,
                    adjust=adjust,
                )
        except Exception as exc:
            logger.error("股票Agent: 分析历史行情失败, error=%s", str(exc))
            return {"symbol": symbol, "rows": 0, "error": str(exc)}

        if df is None or len(df) == 0:
            logger.warning(
                "股票Agent: 分析历史行情为空, symbol=%s, normalized=%s, start=%s, end=%s, period=%s, adjust=%s",
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
        logger.info("股票Agent: 分析历史行情完成, rows=%s", len(df))
        return analysis

    def analyze_technical_indicators(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        period: str = "daily",
        adjust: str = "",
        ma_windows: Optional[list] = None,
    ) -> Dict:
        """
        计算基础技术指标（MA/趋势/动量）
        Args:
            symbol: 股票代码
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            period: 周期 ('daily', 'weekly', 'monthly')
            adjust: 复权类型 (""/"qfq"/"hfq")
            ma_windows: 均线窗口列表

        Returns:
            技术指标摘要
        """
        start = start_date or self.default_start_date
        end = end_date or self.default_end_date
        norm_symbol = self._normalize_symbol(symbol)
        logger.info(
            "股票Agent: 计算技术指标, symbol=%s, normalized=%s, start=%s, end=%s, period=%s, adjust=%s",
            symbol,
            norm_symbol,
            start,
            end,
            period,
            adjust,
        )

        try:
            with self._without_proxy():
                df = self._fetch_hist_with_fallback(
                    symbol=norm_symbol,
                    start_date=start,
                    end_date=end,
                    period=period,
                    adjust=adjust,
                )
        except Exception as exc:
            logger.error("股票Agent: 技术指标失败, error=%s", str(exc))
            return {"symbol": symbol, "rows": 0, "error": str(exc)}

        if df is None or len(df) == 0:
            logger.warning(
                "股票Agent: 技术指标数据为空, symbol=%s, normalized=%s, start=%s, end=%s, period=%s, adjust=%s",
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
        logger.info("股票Agent: 技术指标完成, rows=%s", len(df))
        return result

    def summarize(self, symbol: str) -> Dict:
        """
        汇总股票基础信息与技术指标

        Args:
            symbol: 股票代码

        Returns:
            汇总字典
        """
        logger.info("股票Agent: 汇总开始, symbol=%s", symbol)
        analysis = self.analyze_daily_hist(symbol=symbol)
        technical = self.analyze_technical_indicators(symbol=symbol)
        return {
            "symbol": symbol,
            "analysis": analysis,
            "technical": technical,
        }
