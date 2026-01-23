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
import pandas as pd
import sys
import time


def test_api(func, func_name, *args, **kwargs):
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


def main():
    """主测试函数"""
    print("开始测试AKShare A股接口...")
    print("=" * 50)
    
    # 记录成功和失败的测试数量
    success_count = 0
    fail_count = 0
    
    # 1. 股票市场总貌接口测试
    print("\n【股票市场总貌接口测试】")
    
    # 上海证券交易所-股票数据总貌
    if test_api(ak.stock_sse_summary, "stock_sse_summary"):
        success_count += 1
    else:
        fail_count += 1
    
    # 深圳证券交易所-市场总貌-证券类别统计 (使用当前日期)
    try:
        import datetime
        current_date = datetime.datetime.now().strftime("%Y%m%d")
        if test_api(ak.stock_szse_summary, "stock_szse_summary", date=current_date):
            success_count += 1
        else:
            fail_count += 1
    except Exception as e:
        print(f"✗ stock_szse_summary 调用失败: {str(e)}")
        fail_count += 1
    
    # 深圳证券交易所-市场总貌-地区交易排序 (使用当前年月)
    try:
        import datetime
        current_month = datetime.datetime.now().strftime("%Y%m")
        if test_api(ak.stock_szse_area_summary, "stock_szse_area_summary", date=current_month):
            success_count += 1
        else:
            fail_count += 1
    except Exception as e:
        print(f"✗ stock_szse_area_summary 调用失败: {str(e)}")
        fail_count += 1
    
    # 深圳证券交易所-统计资料-股票行业成交数据 (当月)
    try:
        import datetime
        current_month = datetime.datetime.now().strftime("%Y%m")
        if test_api(ak.stock_szse_sector_summary, "stock_szse_sector_summary", symbol="当月", date=current_month):
            success_count += 1
        else:
            fail_count += 1
    except Exception as e:
        print(f"✗ stock_szse_sector_summary 调用失败: {str(e)}")
        fail_count += 1
    
    # 上海证券交易所-每日概况 (使用最近交易日)
    try:
        import datetime
        recent_date = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y%m%d")
        if test_api(ak.stock_sse_deal_daily, "stock_sse_deal_daily", date=recent_date):
            success_count += 1
        else:
            fail_count += 1
    except Exception as e:
        print(f"✗ stock_sse_deal_daily 调用失败: {str(e)}")
        fail_count += 1
    
    # 2. 实时行情数据接口测试
    print("\n【实时行情数据接口测试】")
    
    # 沪深京A股实时行情
    if test_api(ak.stock_zh_a_spot_em, "stock_zh_a_spot_em"):
        success_count += 1
    else:
        fail_count += 1
    
    # 沪A股实时行情
    if test_api(ak.stock_sh_a_spot_em, "stock_sh_a_spot_em"):
        success_count += 1
    else:
        fail_count += 1
    
    # 深A股实时行情
    if test_api(ak.stock_sz_a_spot_em, "stock_sz_a_spot_em"):
        success_count += 1
    else:
        fail_count += 1
    
    # 京A股实时行情
    if test_api(ak.stock_bj_a_spot_em, "stock_bj_a_spot_em"):
        success_count += 1
    else:
        fail_count += 1
    
    # 新股实时行情
    if test_api(ak.stock_new_a_spot_em, "stock_new_a_spot_em"):
        success_count += 1
    else:
        fail_count += 1
    
    # 创业板实时行情
    if test_api(ak.stock_cy_a_spot_em, "stock_cy_a_spot_em"):
        success_count += 1
    else:
        fail_count += 1
    
    # 科创板实时行情
    if test_api(ak.stock_kc_a_spot_em, "stock_kc_a_spot_em"):
        success_count += 1
    else:
        fail_count += 1
    
    # AB股比价
    if test_api(ak.stock_zh_ab_comparison_em, "stock_zh_ab_comparison_em"):
        success_count += 1
    else:
        fail_count += 1
    
    # 新浪财经-沪深京A股数据 (谨慎测试)
    # 注意：此接口容易被封IP，所以只做简单测试，并添加延迟
    print("正在测试 stock_zh_a_spot (新浪财经)...")
    try:
        time.sleep(2)  # 添加延迟避免被封IP
        result = ak.stock_zh_a_spot()
        if isinstance(result, pd.DataFrame) and len(result) > 0:
            print(f"✓ stock_zh_a_spot 调用成功，返回 {len(result)} 行数据")
            print(result.head(1))  # 只显示一行以减少输出
            success_count += 1
        else:
            print("? stock_zh_a_spot 返回空结果")
        print("-" * 50)
    except Exception as e:
        print(f"✗ stock_zh_a_spot 调用失败: {str(e)}")
        print("-" * 50)
        fail_count += 1
    
    # 雪球-行情中心-个股 (使用示例股票代码)
    if test_api(ak.stock_individual_spot_xq, "stock_individual_spot_xq", symbol="SH600519"):
        success_count += 1
    else:
        fail_count += 1
    
    # 3. 历史行情数据接口测试
    print("\n【历史行情数据接口测试】")
    
    # 东方财富-沪深京A股日频率数据 (使用示例股票代码)
    try:
        if test_api(ak.stock_zh_a_hist, "stock_zh_a_hist", symbol="SH600519", period="daily", 
                   start_date="20230101", end_date="20231231", adjust=""):
            success_count += 1
        else:
            fail_count += 1
    except Exception as e:
        print(f"✗ stock_zh_a_hist 调用失败: {str(e)}")
        fail_count += 1
    
    # 新浪财经-沪深京A股日频率数据 (谨慎测试)
    try:
        if test_api(ak.stock_zh_a_daily, "stock_zh_a_daily", symbol="SH600519", adjust=""):
            success_count += 1
        else:
            fail_count += 1
    except Exception as e:
        print(f"✗ stock_zh_a_daily 调用失败: {str(e)}")
        fail_count += 1
    
    # 腾讯证券-日频-股票历史数据 (使用示例股票代码)
    try:
        if test_api(ak.stock_zh_a_hist_tx, "stock_zh_a_hist_tx", symbol="SH600519", adjust=""):
            success_count += 1
        else:
            fail_count += 1
    except Exception as e:
        print(f"✗ stock_zh_a_hist_tx 调用失败: {str(e)}")
        fail_count += 1
    
    # 4. 分时数据接口测试
    print("\n【分时数据接口测试】")
    
    # 新浪财经-分时数据 (使用示例股票代码)
    try:
        if test_api(ak.stock_zh_a_minute, "stock_zh_a_minute", symbol="SH600519", period="5", adjust=""):
            success_count += 1
        else:
            fail_count += 1
    except Exception as e:
        print(f"✗ stock_zh_a_minute 调用失败: {str(e)}")
        fail_count += 1
    
    # 东方财富网-每日分时行情 (使用示例股票代码)
    try:
        if test_api(ak.stock_zh_a_hist_min_em, "stock_zh_a_hist_min_em", symbol="SH600519", period="5", adjust=""):
            success_count += 1
        else:
            fail_count += 1
    except Exception as e:
        print(f"✗ stock_zh_a_hist_min_em 调用失败: {str(e)}")
        fail_count += 1
    
    # 5. 盘前数据接口测试
    print("\n【盘前数据接口测试】")
    
    # 东方财富-股票行情-盘前数据 (使用示例股票代码)
    if test_api(ak.stock_zh_a_hist_pre_min_em, "stock_zh_a_hist_pre_min_em", symbol="SH600519"):
        success_count += 1
    else:
        fail_count += 1
    
    # 6. 历史分笔数据接口测试
    print("\n【历史分笔数据接口测试】")
    
    # 腾讯财经-历史分笔行情数据 (使用示例股票代码和日期)
    try:
        import datetime
        recent_date = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y%m%d")
        if test_api(ak.stock_zh_a_tick_tx, "stock_zh_a_tick_tx", symbol="SH600519", trade_date=recent_date):
            success_count += 1
        else:
            fail_count += 1
    except Exception as e:
        print(f"✗ stock_zh_a_tick_tx 调用失败: {str(e)}")
        fail_count += 1
    
    # 7. 日内分时数据接口测试
    print("\n【日内分时数据接口测试】")
    
    # 东方财富-分时数据 (使用示例股票代码)
    if test_api(ak.stock_intraday_em, "stock_intraday_em", symbol="SH600519"):
        success_count += 1
    else:
        fail_count += 1
    
    # 新浪财经-日内分时数据 (使用示例股票代码和日期)
    try:
        import datetime
        recent_date = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y%m%d")
        if test_api(ak.stock_intraday_sina, "stock_intraday_sina", symbol="SH600519", date=recent_date):
            success_count += 1
        else:
            fail_count += 1
    except Exception as e:
        print(f"✗ stock_intraday_sina 调用失败: {str(e)}")
        fail_count += 1
    
    # 8. 个股信息查询接口测试
    print("\n【个股信息查询接口测试】")
    
    # 东方财富-个股-股票信息 (使用示例股票代码)
    if test_api(ak.stock_individual_info_em, "stock_individual_info_em", symbol="SH600519"):
        success_count += 1
    else:
        fail_count += 1
    
    # 雪球财经-个股-公司概况-公司简介 (使用示例股票代码)
    if test_api(ak.stock_individual_basic_info_xq, "stock_individual_basic_info_xq", symbol="SH600519"):
        success_count += 1
    else:
        fail_count += 1
    
    # 9. 行情报价接口测试
    print("\n【行情报价接口测试】")
    
    # 东方财富-行情报价 (使用示例股票代码)
    if test_api(ak.stock_bid_ask_em, "stock_bid_ask_em", symbol="SH600519"):
        success_count += 1
    else:
        fail_count += 1
    
    # 10. 同行比较接口测试
    print("\n【同行比较接口测试】")
    
    # 成长性比较
    if test_api(ak.stock_zh_growth_comparison_em, "stock_zh_growth_comparison_em"):
        success_count += 1
    else:
        fail_count += 1
    
    # 估值比较
    if test_api(ak.stock_zh_valuation_comparison_em, "stock_zh_valuation_comparison_em"):
        success_count += 1
    else:
        fail_count += 1
    
    # 杜邦分析比较
    if test_api(ak.stock_zh_dupont_comparison_em, "stock_zh_dupont_comparison_em"):
        success_count += 1
    else:
        fail_count += 1
    
    # 公司规模
    if test_api(ak.stock_zh_scale_comparison_em, "stock_zh_scale_comparison_em"):
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