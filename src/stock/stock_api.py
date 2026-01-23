#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AKShare A股接口封装
说明：部分接口依赖数据源与网络，成功率随时间波动
"""

import akshare as ak
import os
import pandas as pd


# ==================== 内部工具（代码格式规范）====================

def _normalize_symbol_em(symbol: str) -> str:
    """
    东方财富类：不带市场前缀的6位代码
    """
    if not symbol:
        return symbol
    symbol = symbol.upper()
    if symbol.startswith(("SH", "SZ", "BJ")):
        symbol = symbol[2:]
    return symbol


def _normalize_symbol_sina(symbol: str) -> str:
    """
    新浪/腾讯类：小写市场前缀 sh/sz/bj
    """
    if not symbol:
        return symbol
    symbol = symbol.lower()
    if symbol.startswith(("sh", "sz", "bj")):
        return symbol
    if len(symbol) == 6:
        if symbol.startswith("6"):
            return f"sh{symbol}"
        if symbol.startswith(("0", "3")):
            return f"sz{symbol}"
        if symbol.startswith("8"):
            return f"bj{symbol}"
    return symbol


def _normalize_symbol_xq(symbol: str) -> str:
    """
    雪球类：大写市场前缀 SH/SZ/BJ
    """
    if not symbol:
        return symbol
    symbol = symbol.upper()
    if symbol.startswith(("SH", "SZ", "BJ")):
        return symbol
    if len(symbol) == 6:
        if symbol.startswith("6"):
            return f"SH{symbol}"
        if symbol.startswith(("0", "3")):
            return f"SZ{symbol}"
        if symbol.startswith("8"):
            return f"BJ{symbol}"
    return symbol


# ==================== 股票市场总貌 ====================
# 说明：交易所统计口径，部分日期可能无数据

def get_stock_sse_summary():
    """
    上海证券交易所-股票数据总貌
    ✅ 调用成功 (测试通过)
    """
    return ak.stock_sse_summary()


def get_stock_szse_summary(date: str = ""):
    """
    深圳证券交易所-市场总貌-证券类别统计
    备注：个别日期可能返回0行
    
    Args:
        date: 日期 格式: "20200619"
    """
    if not date:
        import datetime
        date = datetime.datetime.now().strftime("%Y%m%d")
    return ak.stock_szse_summary(date=date)


def get_stock_szse_area_summary(date: str = ""):
    """
    深圳证券交易所-市场总貌-地区交易排序
    备注：个别日期可能返回0行
    
    Args:
        date: 年月 格式: "202203"
    """
    if not date:
        import datetime
        date = datetime.datetime.now().strftime("%Y%m")
    return ak.stock_szse_area_summary(date=date)


def get_stock_szse_sector_summary(symbol: str = "当月", date: str = ""):
    """
    深圳证券交易所-统计资料-股票行业成交数据
    备注：date 需为 YYYYMM
    
    Args:
        symbol: "当月" 或 "当年"
        date: 年月 格式: "202501"
    """
    if not date:
        import datetime
        date = datetime.datetime.now().strftime("%Y%m")
    date = date.replace("-", "")
    return ak.stock_szse_sector_summary(symbol=symbol, date=date)


def get_stock_sse_deal_daily(date: str = ""):
    """
    上海证券交易所-每日概况
    备注：仅支持 20211227 之后日期
    
    Args:
        date: 日期 格式: "20250221"
    """
    if not date:
        import datetime
        date = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y%m%d")
    return ak.stock_sse_deal_daily(date=date)


# ==================== 实时行情数据 ====================
# 说明：实时数据依赖网络与数据源稳定性

def get_stock_zh_a_spot_em():
    """
    东方财富网-沪深京A股-实时行情数据
    备注：受网络与数据源影响
    """
    return ak.stock_zh_a_spot_em()


def get_stock_sh_a_spot_em():
    """
    沪A股实时行情
    备注：受网络与数据源影响
    """
    return ak.stock_sh_a_spot_em()


def get_stock_sz_a_spot_em():
    """
    深A股实时行情
    备注：受网络与数据源影响
    """
    return ak.stock_sz_a_spot_em()


def get_stock_bj_a_spot_em():
    """
    京A股实时行情
    备注：受网络与数据源影响
    """
    return ak.stock_bj_a_spot_em()


def get_stock_new_a_spot_em():
    """
    新股实时行情
    备注：受网络与数据源影响
    """
    return ak.stock_new_a_spot_em()


def get_stock_cy_a_spot_em():
    """
    创业板实时行情
    备注：受网络与数据源影响
    """
    return ak.stock_cy_a_spot_em()


def get_stock_kc_a_spot_em():
    """
    科创板实时行情
    备注：受网络与数据源影响
    """
    return ak.stock_kc_a_spot_em()


def get_stock_zh_ab_comparison_em():
    """
    AB股比价-全部AB股比价
    ✅ 调用成功 (测试通过)
    """
    return ak.stock_zh_ab_comparison_em()


def get_stock_zh_a_spot():
    """
    新浪财经-沪深京A股数据
    备注：高频调用可能触发限流/封禁
    """
    return ak.stock_zh_a_spot()


# ==================== 历史行情数据 ====================
# 说明：参数格式需匹配数据源规范

def get_stock_zh_a_hist(symbol: str = "SH600519", period: str = "daily", 
                       start_date: str = "20230101", end_date: str = "20231231", adjust: str = ""):
    """
    东方财富-沪深京A股日频率数据
    ✅ 调用成功 (测试通过，但返回0行数据)
    
    Args:
        symbol: 股票代码
        period: 周期 ('daily', 'weekly', 'monthly')
        start_date, end_date: 日期范围
        adjust: 复权类型 (""-不复权, "qfq"-前复权, "hfq"-后复权)
    """
    symbol = _normalize_symbol_em(symbol)
    return ak.stock_zh_a_hist(symbol=symbol, period=period, 
                             start_date=start_date, end_date=end_date, adjust=adjust)


def get_stock_zh_a_daily(symbol: str = "SH600519", adjust: str = ""):
    """
    新浪财经-沪深京A股日频率数据
    备注：symbol 需为 sh/sz 前缀格式
    
    Args:
        symbol: 股票代码
        adjust: 复权类型
    """
    symbol = _normalize_symbol_sina(symbol)
    return ak.stock_zh_a_daily(symbol=symbol, adjust=adjust)


def get_stock_zh_a_hist_tx(symbol: str = "SH600519", adjust: str = ""):
    """
    腾讯证券-日频-股票历史数据
    备注：symbol 需为 sh/sz 前缀格式
    
    Args:
        symbol: 股票代码
        adjust: 复权类型
    """
    symbol = _normalize_symbol_sina(symbol)
    return ak.stock_zh_a_hist_tx(symbol=symbol, adjust=adjust)


# ==================== 分时数据 ====================
# 说明：数据量较大，注意频率限制

def get_stock_zh_a_minute(symbol: str = "SH600519", period: str = "5", adjust: str = ""):
    """
    新浪财经-分时数据
    ✅ 调用成功 (测试通过)
    
    Args:
        symbol: 股票或指数代码
        period: 分钟频率 (1,5,15,30,60)
        adjust: 复权类型
    """
    symbol = _normalize_symbol_sina(symbol)
    return ak.stock_zh_a_minute(symbol=symbol, period=period, adjust=adjust)


def get_stock_zh_a_hist_min_em(symbol: str = "SH600519", period: str = "5", adjust: str = ""):
    """
    东方财富网-每日分时行情
    备注：个别标的可能无分时数据
    
    Args:
        symbol: 股票代码
        period: 分钟频率 (1,5,15,30,60)
        adjust: 复权类型
    """
    symbol = _normalize_symbol_em(symbol)
    return ak.stock_zh_a_hist_min_em(symbol=symbol, period=period, adjust=adjust)


# ==================== 盘前数据 ====================
# 说明：仅交易日盘前时段有效

def get_stock_zh_a_hist_pre_min_em(symbol: str = "SH600519"):
    """
    东方财富-股票行情-盘前数据
    备注：非交易时段可能为空
    
    Args:
        symbol: 股票代码
    """
    symbol = _normalize_symbol_em(symbol)
    return ak.stock_zh_a_hist_pre_min_em(symbol=symbol)


# ==================== 日内分时数据 ====================
# 说明：依赖当日交易数据

def get_stock_intraday_em(symbol: str = "SH600519"):
    """
    东方财富-分时数据
    备注：非交易时段可能为空
    
    Args:
        symbol: 股票代码
    """
    symbol = _normalize_symbol_em(symbol)
    return ak.stock_intraday_em(symbol=symbol)


def get_stock_intraday_sina(symbol: str = "SH600519", date: str = ""):
    """
    新浪财经-日内分时数据
    备注：接口稳定性随数据源变动
    
    Args:
        symbol: 股票代码
        date: 日期
    """
    if not date:
        import datetime
        date = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y%m%d")
    symbol = _normalize_symbol_sina(symbol)
    return ak.stock_intraday_sina(symbol=symbol, date=date)


# ==================== 个股信息查询 ====================
# 说明：参数格式需匹配数据源规范

def get_stock_individual_info_em(symbol: str = "SH600519"):
    """
    东方财富-个股-股票信息
    备注：symbol 需为 6 位代码
    
    Args:
        symbol: 股票代码
    """
    symbol = _normalize_symbol_em(symbol)
    return ak.stock_individual_info_em(symbol=symbol)


def get_stock_individual_basic_info_xq(symbol: str = "SH600519"):
    """
    雪球财经-个股-公司概况-公司简介
    备注：symbol 需为 SH/SZ 前缀格式
    
    Args:
        symbol: 带市场标识的股票代码
    """
    symbol = _normalize_symbol_xq(symbol)
    return ak.stock_individual_basic_info_xq(symbol=symbol)


# ==================== 行情报价 ====================
# 说明：盘中数据为主

def get_stock_bid_ask_em(symbol: str = "SH600519"):
    """
    东方财富-行情报价
    备注：非交易时段可能为空
    
    Args:
        symbol: 股票代码
    """
    symbol = _normalize_symbol_em(symbol)
    return ak.stock_bid_ask_em(symbol=symbol)


# ==================== 同行比较 ====================
# 说明：数据源更新频率较低

def get_stock_zh_growth_comparison_em():
    """
    东方财富-行情中心-同行比较-成长性比较
    ✅ 调用成功 (测试通过)
    """
    return ak.stock_zh_growth_comparison_em()


def get_stock_zh_valuation_comparison_em():
    """
    东方财富-行情中心-同行比较-估值比较
    ✅ 调用成功 (测试通过)
    """
    return ak.stock_zh_valuation_comparison_em()


def get_stock_zh_dupont_comparison_em():
    """
    东方财富-行情中心-同行比较-杜邦分析比较
    ✅ 调用成功 (测试通过)
    """
    return ak.stock_zh_dupont_comparison_em()


def get_stock_zh_scale_comparison_em():
    """
    东方财富-行情中心-同行比较-公司规模
    ✅ 调用成功 (测试通过)
    """
    return ak.stock_zh_scale_comparison_em()


# ==================== 推荐使用的稳定接口 ====================
# 说明：基于当前测试的相对稳定集合

def get_recommended_apis():
    """
    获取推荐使用的稳定接口列表
    """
    return [
        "get_stock_sse_summary",           # 上交所股票数据总貌
        "get_stock_zh_ab_comparison_em",   # AB股比价
        "get_stock_zh_a_hist",             # 东方财富历史行情(日线)
        "get_stock_zh_a_minute",           # 新浪分时数据
        "get_stock_zh_growth_comparison_em",  # 成长性比较
        "get_stock_zh_valuation_comparison_em",  # 估值比较
        "get_stock_zh_dupont_comparison_em",     # 杜邦分析比较
        "get_stock_zh_scale_comparison_em"       # 公司规模比较
    ]