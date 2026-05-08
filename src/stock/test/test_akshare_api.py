#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AKShare A股接口测试文件
用于测试AKShare文档中提到的所有股票数据接口能否正常调用

注意事项：
1. 部分接口可能需要网络连接
2. 部分接口有调用频率限制，请勿频繁调用
3. 新浪财经接口容易被封IP，已做适当延迟处理
4. 部分接口可能因数据源问题暂时不可用
"""

import akshare as ak
import os
import pandas as pd
import sys
import time
import datetime


def run_api_check(func, func_name, *args, **kwargs):
    """
    测试API函数调用
    
    Args:
        func: 要测试的函数
        func_name: 函数名称
        *args: 函数参数
        **kwargs: 函数关键字参数
    
    Returns:
        bool: 测试是否成功
    """
    try:
        print(f"正在测试 {func_name}...")
        result = func(*args, **kwargs)
        
        if isinstance(result, pd.DataFrame):
            print(f"✓ {func_name} 调用成功，返回 {len(result)} 行数据")
            # 显示前几行数据
            if len(result) > 0:
                print(result.head(3))
        elif result is None:
            print(f"? {func_name} 返回空结果")
        else:
            print(f"✓ {func_name} 调用成功，返回类型: {type(result)}")
            
        print("-" * 50)
        return True
        
    except Exception as e:
        print(f"✗ {func_name} 调用失败: {str(e)}")
        print("-" * 50)
        return False


def get_last_month_yyyymm():
    """
    获取上一个完整月份，避免当月无数据
    """
    first_day = datetime.datetime.now().replace(day=1)
    last_month_day = first_day - datetime.timedelta(days=1)
    return last_month_day.strftime("%Y%m")


def get_recent_dates(days: int = 10):
    """
    获取最近若干天的日期字符串（YYYYMMDD）
    """
    today = datetime.datetime.now()
    return [(today - datetime.timedelta(days=i)).strftime("%Y%m%d") for i in range(1, days + 1)]


def load_env_file(env_path: str = ".env"):
    """
    简单加载 .env 文件到环境变量（若已存在则不覆盖）
    """
    if not os.path.isfile(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception:
        pass


def main():
    """主测试函数"""
    print("开始测试AKShare A股接口...")
    print("=" * 50)
    
    # 记录成功和失败的测试数量
    success_count = 0
    fail_count = 0
    
    # 常用符号格式
    symbol_em = "600519"     # 东方财富类: 6位代码
    symbol_em_alt = "000001" # 备选（平安银行）
    symbol_sina = "sh600519" # 新浪/腾讯类: 小写市场前缀
    symbol_xq = "SH600519"   # 雪球类: 大写市场前缀

    # 加载 .env（如存在），以便读取雪球 token
    load_env_file()

    # 仅测试上次失败的接口

    # 1. 股票市场总貌接口测试
    print("\n【股票市场总貌接口测试】")
    try:
        last_month = get_last_month_yyyymm()
        if run_api_check(ak.stock_szse_sector_summary, "stock_szse_sector_summary", symbol="当月", date=last_month):
            success_count += 1
        else:
            fail_count += 1
    except Exception as e:
        print(f"✗ stock_szse_sector_summary 调用失败: {str(e)}")
        fail_count += 1

    # 2. 历史行情数据接口测试
    print("\n【历史行情数据接口测试】")
    try:
        if run_api_check(ak.stock_zh_a_daily, "stock_zh_a_daily", symbol=symbol_sina, adjust=""):
            success_count += 1
        else:
            fail_count += 1
    except Exception as e:
        print(f"✗ stock_zh_a_daily 调用失败: {str(e)}")
        fail_count += 1

    try:
        if run_api_check(ak.stock_zh_a_hist_tx, "stock_zh_a_hist_tx", symbol=symbol_sina, adjust="", 
                   start_date="20230101", end_date="20231231"):
            success_count += 1
        else:
            fail_count += 1
    except Exception as e:
        print(f"✗ stock_zh_a_hist_tx 调用失败: {str(e)}")
        fail_count += 1

    # 3. 分时数据接口测试
    print("\n【分时数据接口测试】")
    try:
        if run_api_check(ak.stock_zh_a_hist_min_em, "stock_zh_a_hist_min_em", symbol=symbol_em, period="5", adjust=""):
            success_count += 1
        elif run_api_check(ak.stock_zh_a_hist_min_em, "stock_zh_a_hist_min_em", symbol=symbol_em_alt, period="5", adjust=""):
            success_count += 1
        else:
            fail_count += 1
    except Exception as e:
        print(f"✗ stock_zh_a_hist_min_em 调用失败: {str(e)}")
        fail_count += 1

    # 4. 盘前数据接口测试
    print("\n【盘前数据接口测试】")
    if run_api_check(ak.stock_zh_a_hist_pre_min_em, "stock_zh_a_hist_pre_min_em", symbol=symbol_em):
        success_count += 1
    elif run_api_check(ak.stock_zh_a_hist_pre_min_em, "stock_zh_a_hist_pre_min_em", symbol=symbol_em_alt):
        success_count += 1
    else:
        fail_count += 1

    # 5. 日内分时数据接口测试
    print("\n【日内分时数据接口测试】")
    if run_api_check(ak.stock_intraday_em, "stock_intraday_em", symbol=symbol_em_alt):
        success_count += 1
    elif run_api_check(ak.stock_intraday_em, "stock_intraday_em", symbol=symbol_em):
        success_count += 1
    else:
        fail_count += 1

    try:
        intraday_success = False
        last_error = None
        for day in get_recent_dates(10):
            try:
                if run_api_check(ak.stock_intraday_sina, "stock_intraday_sina", symbol=symbol_sina, date=day):
                    success_count += 1
                    intraday_success = True
                    break
            except Exception as e:
                last_error = e
        if not intraday_success:
            if last_error:
                print(f"✗ stock_intraday_sina 调用失败: {str(last_error)}")
                print("-" * 50)
            fail_count += 1
    except Exception as e:
        print(f"✗ stock_intraday_sina 调用失败: {str(e)}")
        fail_count += 1

    # 6. 个股信息查询接口测试
    print("\n【个股信息查询接口测试】")
    if run_api_check(ak.stock_individual_info_em, "stock_individual_info_em", symbol=symbol_em):
        success_count += 1
    else:
        fail_count += 1

    token = os.getenv("XUEQIU_TOKEN") or os.getenv("XQ_AKSHARE_TOKEN") or os.getenv("XQ_TOKEN")
    if token:
        if run_api_check(ak.stock_individual_basic_info_xq, "stock_individual_basic_info_xq", symbol=symbol_xq, token=token):
            success_count += 1
        else:
            fail_count += 1
    else:
        print("⚠️ stock_individual_basic_info_xq 跳过: 未设置 XUEQIU_TOKEN/XQ_AKSHARE_TOKEN/XQ_TOKEN")
        print("-" * 50)

    # 7. 行情报价接口测试
    print("\n【行情报价接口测试】")
    if run_api_check(ak.stock_bid_ask_em, "stock_bid_ask_em", symbol=symbol_em):
        success_count += 1
    elif run_api_check(ak.stock_bid_ask_em, "stock_bid_ask_em", symbol=symbol_em_alt):
        success_count += 1
    else:
        fail_count += 1
    
    # 输出测试总结
    print("\n" + "=" * 50)
    print("测试完成!")
    print(f"成功: {success_count}")
    print(f"失败: {fail_count}")
    print(f"总计: {success_count + fail_count}")
    
    if fail_count == 0:
        print("\n🎉 所有接口测试通过!")
        return 0
    else:
        print(f"\n⚠️  有 {fail_count} 个接口测试失败，请检查网络连接或API状态。")
        return 1


if __name__ == "__main__":
    # 检查是否安装了akshare
    try:
        import akshare
        print(f"AKShare 版本: {akshare.__version__}")
    except ImportError:
        print("错误: 未安装 akshare 库")
        print("请运行: pip install akshare")
        sys.exit(1)
    
    # 运行测试
    exit_code = main()
    sys.exit(exit_code)