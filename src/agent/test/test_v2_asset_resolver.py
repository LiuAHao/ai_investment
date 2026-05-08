#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
V2 多资产识别测试
"""

import os
import sys

CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_SRC = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
if PROJECT_SRC not in sys.path:
    sys.path.insert(0, PROJECT_SRC)

from agent.v2.asset_resolver import _resolve_assets_internal
from agent.v2.state import Asset, AssetResolveInput, AssetType, IntentResult


def _resolve(query: str, intent: str = "asset_analysis"):
    return _resolve_assets_internal(
        AssetResolveInput(
            query=query,
            intent=IntentResult(primary_intent=intent),
        )
    )


def test_resolve_cn_stock_by_name():
    """中文股票名称应从资产主数据解析为 A 股资产"""
    result = _resolve("分析宁德时代未来三个月风险")

    assert len(result.selected_assets) == 1
    assert result.selected_assets[0].asset_id == "cn_stock:300750"
    assert result.selected_assets[0].asset_type == AssetType.CN_STOCK
    assert not result.ambiguous


def test_resolve_us_stock_by_ticker():
    """美股 ticker 应解析为美股资产"""
    result = _resolve("分析 AAPL 的长期风险")

    assert len(result.selected_assets) == 1
    assert result.selected_assets[0].asset_id == "us_stock:AAPL"
    assert result.selected_assets[0].asset_type == AssetType.US_STOCK


def test_resolve_etf_by_alias():
    """ETF 别名应解析为 ETF 资产"""
    result = _resolve("沪深300ETF 怎么看")

    assert len(result.selected_assets) == 1
    assert result.selected_assets[0].asset_id == "etf:510300"
    assert result.selected_assets[0].asset_type == AssetType.ETF


def test_resolve_fund_code_without_hk_false_positive():
    """6位基金代码不应被误切为5位港股代码"""
    result = _resolve("000001 基金风险如何")

    assert len(result.selected_assets) == 1
    assert result.selected_assets[0].asset_id == "fund:000001"
    assert result.selected_assets[0].asset_type == AssetType.FUND
    assert not any(item.asset_id == "hk_stock:00000" for item in result.candidates)


def test_ambiguous_name_requires_clarification():
    """歧义名称应返回候选资产，避免强行分析"""
    result = _resolve("分析平安")

    assert result.ambiguous
    assert result.need_user_clarification
    assert not result.selected_assets
    assert {item.asset_id for item in result.candidates} >= {"cn_stock:601318", "cn_stock:000001"}


def test_follow_up_inherits_previous_asset():
    """追问场景应继承上一轮资产"""
    previous = Asset(
        asset_id="cn_stock:300750",
        asset_type=AssetType.CN_STOCK,
        symbol="300750",
        name="宁德时代",
    )
    result = _resolve_assets_internal(
        AssetResolveInput(
            query="那如果持有三个月呢",
            previous_assets=[previous],
            intent=IntentResult(primary_intent="follow_up"),
        )
    )

    assert result.selected_assets == [previous]
    assert "追问继承" in result.reason
