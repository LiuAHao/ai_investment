#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
StockAgent 回退链路测试
"""

import os
import sys

import pandas as pd

CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_SRC = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
if PROJECT_SRC not in sys.path:
    sys.path.insert(0, PROJECT_SRC)

from agent.stock_agent import StockAgent
import agent.stock_agent as stock_agent_module


def test_fallback_when_primary_source_raises(monkeypatch):
    """当主数据源异常时，应继续回退到腾讯/新浪数据源"""

    sample_df = pd.DataFrame(
        [
            {"日期": "2026-02-11", "收盘": 10.0, "开盘": 9.8, "最高": 10.2, "最低": 9.7},
            {"日期": "2026-02-12", "收盘": 10.5, "开盘": 10.1, "最高": 10.6, "最低": 10.0},
        ]
    )

    def mock_hist_raise(**kwargs):
        raise RuntimeError("primary source error")

    def mock_hist_tx(**kwargs):
        return sample_df

    def mock_daily(**kwargs):
        return None

    monkeypatch.setattr(stock_agent_module, "get_stock_zh_a_hist", mock_hist_raise)
    monkeypatch.setattr(stock_agent_module, "get_stock_zh_a_hist_tx", mock_hist_tx)
    monkeypatch.setattr(stock_agent_module, "get_stock_zh_a_daily", mock_daily)

    agent = StockAgent(default_start_date="20260101", default_end_date="20260212")
    result = agent.analyze_daily_hist(symbol="002378")

    assert result.get("rows") == 2
    assert result.get("symbol") == "002378"
    assert "error" not in result


def test_fallback_to_third_source_when_first_two_empty(monkeypatch):
    """当东方财富和腾讯为空时，应回退到新浪数据源"""

    sample_df = pd.DataFrame(
        [
            {"日期": "2026-02-11", "收盘": 10.0, "开盘": 9.8, "最高": 10.2, "最低": 9.7},
            {"日期": "2026-02-12", "收盘": 10.2, "开盘": 10.0, "最高": 10.3, "最低": 9.9},
        ]
    )

    def mock_hist_empty(**kwargs):
        return pd.DataFrame()

    def mock_hist_tx_empty(**kwargs):
        return pd.DataFrame()

    def mock_daily_ok(**kwargs):
        return sample_df

    monkeypatch.setattr(stock_agent_module, "get_stock_zh_a_hist", mock_hist_empty)
    monkeypatch.setattr(stock_agent_module, "get_stock_zh_a_hist_tx", mock_hist_tx_empty)
    monkeypatch.setattr(stock_agent_module, "get_stock_zh_a_daily", mock_daily_ok)

    agent = StockAgent(default_start_date="20260101", default_end_date="20260212")
    result = agent.analyze_technical_indicators(symbol="002378")

    assert result.get("rows") == 2
    assert result.get("symbol") == "002378"
    assert result.get("latest_close") == 10.2
    assert "error" not in result
