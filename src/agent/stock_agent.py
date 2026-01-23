#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
股票 Agent：获取与分析行情数据
"""

from typing import Dict, Optional

import logging

import pandas as pd

logger = logging.getLogger(__name__)

from stock.stock_api import get_stock_zh_a_hist


class StockAgent:
    """股票 Agent"""

    def __init__(self, default_start_date: str = "20230101", default_end_date: str = "20231231"):
        self.default_start_date = default_start_date
        self.default_end_date = default_end_date

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
        logger.info(
            "股票Agent: 获取历史行情, symbol=%s, start=%s, end=%s, period=%s, adjust=%s",
            symbol,
            start,
            end,
            period,
            adjust,
        )
        try:
            df = get_stock_zh_a_hist(
                symbol=symbol,
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
        logger.info(
            "股票Agent: 分析历史行情, symbol=%s, start=%s, end=%s, period=%s, adjust=%s",
            symbol,
            start,
            end,
            period,
            adjust,
        )
        try:
            df = get_stock_zh_a_hist(
                symbol=symbol,
                start_date=start,
                end_date=end,
                period=period,
                adjust=adjust,
            )
        except Exception as exc:
            logger.error("股票Agent: 分析历史行情失败, error=%s", str(exc))
            return {"symbol": symbol, "rows": 0, "error": str(exc)}

        if df is None or len(df) == 0:
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
            技术指标字典
        """
        start = start_date or self.default_start_date
        end = end_date or self.default_end_date
        logger.info(
            "股票Agent: 计算技术指标, symbol=%s, start=%s, end=%s, period=%s, adjust=%s",
            symbol,
            start,
            end,
            period,
            adjust,
        )
        try:
            df = get_stock_zh_a_hist(
                symbol=symbol,
                start_date=start,
                end_date=end,
                period=period,
                adjust=adjust,
            )
        except Exception as exc:
            logger.error("股票Agent: 计算技术指标失败, error=%s", str(exc))
            return {"symbol": symbol, "rows": 0, "error": str(exc)}

        if df is None or len(df) == 0:
            return {"symbol": symbol, "rows": 0}

        def pick_col(candidates):
            for col in candidates:
                if col in df.columns:
                    return col
            return None

        close_col = pick_col(["收盘", "close"])
        if not close_col:
            return {"symbol": symbol, "rows": len(df), "error": "缺少收盘价字段"}

        ma_windows = ma_windows or [5, 10, 20, 60]
        close_series = pd.Series(df[close_col])
        latest_close = float(close_series.iloc[-1])

        ma_values = {}
        for w in ma_windows:
            if len(close_series) >= w:
                ma_values[f"ma_{w}"] = round(float(close_series.rolling(w).mean().iloc[-1]), 4)

        trend = None
        if "ma_5" in ma_values and "ma_20" in ma_values:
            if ma_values["ma_5"] > ma_values["ma_20"]:
                trend = "上行"
            elif ma_values["ma_5"] < ma_values["ma_20"]:
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
