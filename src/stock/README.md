# stock 模块简介

stock 模块基于 AkShare 封装 A 股数据接口，提供行情、历史数据、分时数据、个股信息与市场统计等能力，便于上层 Agent 统一调用。

## 功能概览

- 市场总貌与交易所统计
- 实时行情与分市场行情
- 历史行情（日线/周线/月线）
- 分时/盘前/日内分时数据
- 个股基础信息与行情报价
- 同行比较与估值/成长性分析

## 目录与职责

- stock_api.py：AkShare A 股接口封装
- test_akshare_api.py：接口可用性测试脚本（按数据源稳定性结果标注）
- requirements.txt：stock 子模块依赖

## 依赖安装

在项目根目录安装依赖后即可使用。

## 接口分类（对应 stock_api.py）

### 市场总貌

- `get_stock_sse_summary()`：上交所股票数据总貌
- `get_stock_szse_summary(date)`：深交所市场总貌
- `get_stock_szse_area_summary(date)`：深交所地区交易排序
- `get_stock_szse_sector_summary(symbol, date)`：深交所行业成交统计
- `get_stock_sse_deal_daily(date)`：上交所每日概况

### 实时行情

- `get_stock_zh_a_spot_em()`：沪深京 A 股实时行情
- `get_stock_sh_a_spot_em()` / `get_stock_sz_a_spot_em()` / `get_stock_bj_a_spot_em()`
- `get_stock_new_a_spot_em()` / `get_stock_cy_a_spot_em()` / `get_stock_kc_a_spot_em()`
- `get_stock_zh_a_spot()`：新浪财经实时行情（高频可能限流）

### 历史行情

- `get_stock_zh_a_hist(symbol, period, start_date, end_date, adjust)`：东方财富日线/周线/月线
- `get_stock_zh_a_daily(symbol, adjust)`：新浪日线
- `get_stock_zh_a_hist_tx(symbol, adjust)`：腾讯日线

### 分时/盘前/日内

- `get_stock_zh_a_minute(symbol, period, adjust)`：新浪分时
- `get_stock_zh_a_hist_min_em(symbol, period, adjust)`：东方财富分时
- `get_stock_zh_a_hist_pre_min_em(symbol)`：盘前数据
- `get_stock_intraday_em(symbol)` / `get_stock_intraday_sina(symbol, date)`：日内分时

### 个股信息与报价

- `get_stock_individual_info_em(symbol)`：个股信息（东方财富）
- `get_stock_individual_basic_info_xq(symbol)`：公司概况（雪球）
- `get_stock_bid_ask_em(symbol)`：行情报价

### 同行比较

- `get_stock_zh_growth_comparison_em()`：成长性比较
- `get_stock_zh_valuation_comparison_em()`：估值比较
- `get_stock_zh_dupont_comparison_em()`：杜邦分析比较
- `get_stock_zh_scale_comparison_em()`：公司规模比较

## 推荐使用的稳定接口

调用 `get_recommended_apis()` 可获得相对稳定的接口集合，适合优先集成。

## 符号格式规范

模块内部已做统一格式处理：

- 东方财富类：6 位代码（如 600519）
- 新浪/腾讯类：小写前缀（如 sh600519）
- 雪球类：大写前缀（如 SH600519）

调用时可传入常见格式，模块会自动规范化。

## 注意事项

- 部分接口受网络与数据源稳定性影响，返回可能为空
- 实时/高频接口存在限流风险，建议在上层做缓存与降频
- 日期参数需按接口要求格式传入（如 YYYYMMDD / YYYYMM）
