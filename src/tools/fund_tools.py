#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
基金工具
提供基金净值、持仓等数据
数据源优先级：tushare（fund_basic / fund_nav）> akshare 东方财富
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from agents.state import AssetType
from tools.base import BaseTool, CostLevel, RiskLevel

logger = logging.getLogger(__name__)


class FundProfileTool(BaseTool):
    """基金基本信息工具"""

    name = "fund_profile"
    description = "获取基金基本信息、费率、基金经理"
    timeout = 15

    asset_types = [AssetType.FUND]
    intents = ["asset_analysis", "comparison"]
    cost_level = CostLevel.LOW
    risk_level = RiskLevel.LOW

    def execute(self, fund_code: str, **kwargs) -> Dict[str, Any]:
        """获取基金基本信息（tushare 优先，失败回退 akshare）"""
        try:
            from data.tushare_client import get_fund_profile

            profile = get_fund_profile(fund_code)
            if profile:
                return {"fund_code": fund_code, "profile": profile}
        except Exception as e:
            logger.warning("tushare fund_profile 失败 %s, 回退 akshare: %s", fund_code, e)

        try:
            import akshare as ak

            df = ak.fund_open_fund_info_em(symbol=fund_code, indicator="基金概况")
            if df is not None and not df.empty:
                info = {}
                for _, row in df.iterrows():
                    if len(row) >= 2:
                        info[str(row.iloc[0])] = str(row.iloc[1])
                return {"fund_code": fund_code, "profile": info}
        except Exception as e:
            logger.warning("akshare fund_profile 失败 %s: %s", fund_code, e)

        return {
            "fund_code": fund_code,
            "profile": {"基金名称": "", "基金类型": "", "基金经理": ""},
            "note": "基金数据暂不可用",
        }


class FundNavTool(BaseTool):
    """基金净值工具"""

    name = "fund_nav_history"
    description = "获取基金历史净值数据"
    timeout = 15

    asset_types = [AssetType.FUND]
    intents = ["asset_analysis", "risk_check"]
    cost_level = CostLevel.MEDIUM
    freshness_requirement_seconds = 172800
    risk_level = RiskLevel.LOW

    def execute(self, fund_code: str, period: str = "近1月", **kwargs) -> Dict[str, Any]:
        """获取基金净值历史（tushare fund_nav 优先，失败回退 akshare）"""
        try:
            from data.tushare_client import get_fund_nav

            nav_df = get_fund_nav(fund_code, limit=30)
            if nav_df is not None and len(nav_df) > 0:
                rename = {
                    "nav_date": "净值日期",
                    "unit_nav": "单位净值",
                    "accum_nav": "累计净值",
                    "ann_date": "公告日期",
                }
                data = nav_df.rename(columns=rename).to_dict(orient="records")
                return {"fund_code": fund_code, "nav_data": data}
        except Exception as e:
            logger.warning("tushare fund_nav 失败 %s, 回退 akshare: %s", fund_code, e)

        try:
            import akshare as ak

            df = ak.fund_open_fund_info_em(symbol=fund_code, indicator="单位净值走势")
            if df is not None and not df.empty:
                data = df.tail(30).to_dict(orient="records")
                return {"fund_code": fund_code, "nav_data": data}
        except Exception as e:
            logger.warning("akshare fund_nav 失败 %s: %s", fund_code, e)

        return {"fund_code": fund_code, "nav_data": [], "note": "净值数据暂不可用"}
