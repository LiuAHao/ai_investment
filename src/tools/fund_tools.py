#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
基金工具
提供基金净值、持仓等数据
"""

from __future__ import annotations

from typing import Any, Dict

from agent.v2.state import AssetType
from tools.base import BaseTool, CostLevel, RiskLevel


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
        """获取基金基本信息"""
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
            pass
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
        """获取基金净值历史"""
        try:
            import akshare as ak
            df = ak.fund_open_fund_info_em(symbol=fund_code, indicator="单位净值走势")
            if df is not None and not df.empty:
                data = df.tail(30).to_dict(orient="records")
                return {"fund_code": fund_code, "nav_data": data}
        except Exception as e:
            pass
        return {"fund_code": fund_code, "nav_data": [], "note": "净值数据暂不可用"}
