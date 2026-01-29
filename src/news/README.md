# news 模块简介

news 模块用于新闻数据获取与处理，提供 RSS 拉取、解析、清洗与统一封装能力，为上层 Agent 分析与决策提供结构化新闻数据。

## 功能概览

- 支持多 RSS 源聚合拉取
- 兼容 RSS/Atom 常见格式
- HTML 标签清洗与空白规范化
- 发布日期解析与时区处理
- 统一 `NewsItem` 数据结构输出

## 目录与职责

- news_api.py：新闻接口封装、解析与数据处理核心逻辑
- requirements.txt：news 子模块依赖

## 核心数据结构

- `NewsItem`：新闻项数据类，包含 `title`、`link`、`description`、`pub_date`、`source`

## 主要接口

- `RSSNewsParser`：内部解析器
	- `parse_rss_feed(rss_url, source_name=None)`：解析单个 RSS 源并返回 `NewsItem` 列表
	- `fetch_titles(rss_urls=None, source_names=None, limit=100)`：聚合拉取标题列表
	- `close()`：关闭网络会话
- `get_news_titles(limit=100, sources=None)`：对外标题获取接口

## 默认数据源

- 财富中文网
- 经济日报

可通过 `get_news_titles` 的 `sources` 参数传入自定义数据源列表。

## 使用方式

在项目根目录安装依赖后，通过上层 Agent 或直接调用 `get_news_titles` 获取新闻标题；如需更多字段，可使用 `RSSNewsParser.parse_rss_feed` 获取完整 `NewsItem` 数据。

## 注意事项

- 网络请求默认带超时，失败会记录日志并跳过
- 日期解析支持多种格式，无法解析时回退为当前 UTC 时间
- 若 RSS 源更新频繁，建议在上层调用侧增加缓存或限频策略
