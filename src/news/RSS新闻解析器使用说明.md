# RSS新闻解析器使用说明

## 概述

本RSS新闻解析器专为AI投资分析系统设计，能够从多个RSS源获取新闻信息，存储到数据库中，并为投资分析Agent提供智能的新闻检索和分析功能。

## 功能特性

### 1. RSS新闻抓取
- 支持标准RSS和Atom格式
- 自动清理HTML标签和CDATA内容
- 智能日期时间解析
- 重复新闻检测和去重
- 多RSS源并发抓取

### 2. 数据库存储
- MySQL数据库支持
- 完整的新闻信息存储（标题、链接、描述、发布时间、来源）
- 自动生成内容哈希用于去重
- 索引优化提高查询性能
- 会话管理和连接池

### 3. Agent集成支持
- 获取最近新闻标题列表
- 基于关键词的新闻相关性分析
- 按需获取新闻详细内容
- 市场情绪新闻筛选
- 财经新闻智能摘要

## 文件结构

```
ai_investment/
├── rss_news_parser.py          # 核心RSS解析器
├── rss_config.py              # 配置文件
├── news_agent_integration.py  # Agent集成模块
├── requirements_news.txt      # 依赖包列表
└── RSS新闻解析器使用说明.md    # 本文档
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements_news.txt
```

### 2. 数据库准备

确保MySQL数据库已创建并运行，根据`rss_config.py`中的配置更新数据库连接信息。

### 3. 基本使用

```python
from rss_news_parser import RSSNewsParser

# 创建解析器实例
parser = RSSNewsParser('mysql+pymysql://user:pass@localhost:3306/database')

# 抓取并存储新闻
results = parser.fetch_and_store_news([
    'https://plink.anyfeeder.com/jingjiribao'
], ['经济日报'])

# 获取最近新闻标题
recent_news = parser.get_news_for_agent(hours=24)

# 关闭解析器
parser.close()
```

### 4. Agent集成使用

```python
from news_agent_integration import NewsAgent

# 创建新闻Agent
agent = NewsAgent()

# 获取财经新闻摘要
summary = agent.get_financial_news_summary(
    stock_symbols=['600519', '000001'],
    sectors=['白酒', '银行']
)

# 分析市场情绪
sentiment_news = agent.get_market_sentiment_news()

# 关闭Agent
agent.close()
```

## 配置说明

### RSS源配置

在`rss_config.py`中配置RSS源：

```python
RSS_SOURCES = [
    {
        'url': 'https://plink.anyfeeder.com/jingjiribao',
        'name': '经济日报',
        'category': '财经',
        'language': 'zh',
        'enabled': True
    }
]
```

### 数据库配置

```python
DATABASE_CONFIG = {
    'mysql_url': 'mysql+pymysql://root:123456@localhost:3306/chat_robot',
    'pool_size': 10,
    'max_overflow': 20,
}
```

### Agent配置

```python
AGENT_CONFIG = {
    'news_history_hours': 24,         # 分析的新闻时间范围
    'max_news_for_analysis': 50,      # 最大分析数量
    'title_matching_threshold': 0.7,  # 标题匹配置信度
}
```

## API接口说明

### RSSNewsParser类

#### 主要方法：

- `parse_rss_feed(rss_url, source_name=None)` - 解析RSS源
- `fetch_and_store_news(rss_urls, source_names=None)` - 抓取并存储新闻
- `get_news_for_agent(hours=24)` - 获取新闻标题列表
- `get_news_details(titles, limit=50)` - 获取新闻详细信息
- `close()` - 关闭解析器

### NewsAgent类

#### 主要方法：

- `get_recent_news_titles(hours=None)` - 获取最近新闻标题
- `analyze_news_relevance(keywords, news_titles)` - 分析新闻相关性
- `get_news_details(titles, limit=None)` - 获取新闻详情
- `get_financial_news_summary(stock_symbols=None, sectors=None)` - 财经新闻摘要
- `get_market_sentiment_news()` - 市场情绪新闻

## 数据库表结构

```sql
CREATE TABLE news_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(500) NOT NULL COMMENT '新闻标题',
    link VARCHAR(1000) UNIQUE NOT NULL COMMENT '新闻链接',
    description TEXT COMMENT '新闻描述',
    pub_date DATETIME NOT NULL COMMENT '发布时间',
    source VARCHAR(100) NOT NULL COMMENT '新闻源',
    content_hash VARCHAR(32) UNIQUE NOT NULL COMMENT '内容哈希',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
);

-- 索引
CREATE INDEX idx_source_pub_date ON news_items(source, pub_date);
CREATE INDEX idx_content_hash ON news_items(content_hash);
CREATE INDEX idx_pub_date ON news_items(pub_date);
```

## 使用流程

### 1. 新闻抓取流程

```
配置RSS源 → 创建解析器 → 抓取RSS内容 → 解析XML结构 → 清理数据 → 存储数据库
```

### 2. Agent分析流程

```
获取新闻标题 → 关键词匹配 → 相关性评分 → 选择重要新闻 → 获取详细内容 → 生成分析报告
```

## 错误处理

- 网络请求失败：自动重试机制
- XML解析错误：跳过无效内容并记录日志
- 数据库连接错误：连接池管理和错误恢复
- 重复数据处理：基于内容哈希自动去重

## 性能优化

- 使用数据库连接池减少连接开销
- 批量插入数据提高写入性能
- 创建适当索引加速查询
- 请求间延迟避免被封禁
- 内容哈希快速去重检测

## 日志记录

程序提供详细的日志记录，包括：
- RSS源抓取状态
- 数据库操作结果
- 错误和警告信息
- 性能统计数据

## 扩展功能

可以根据需要扩展以下功能：
- 支持更多RSS源格式
- 添加新闻情感分析
- 实现新闻分类和标签
- 添加新闻推送通知
- 支持多语言新闻源

## 注意事项

1. **频率限制**：避免过于频繁的RSS请求
2. **版权合规**：遵守新闻源的使用条款
3. **数据备份**：定期备份重要新闻数据
4. **监控告警**：设置异常情况的监控和告警

## 故障排除

### 常见问题：

1. **RSS源无法访问**
   - 检查网络连接
   - 验证RSS源URL是否有效
   - 检查防火墙设置

2. **数据库连接失败**
   - 确认数据库服务运行状态
   - 检查连接字符串配置
   - 验证用户权限设置

3. **重复新闻过多**
   - 检查内容哈希生成逻辑
   - 确认数据库唯一性约束
   - 调整抓取频率设置

## 技术支持

如遇到问题，请检查日志文件获取详细错误信息，并根据错误信息进行相应排查。