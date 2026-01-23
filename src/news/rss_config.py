#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
RSS新闻配置文件
定义RSS源和相关配置
"""

# RSS新闻源配置
RSS_SOURCES = [
    {
        'url': 'https://plink.anyfeeder.com/jingjiribao',
        'name': '经济日报',
        'category': '财经',
        'language': 'zh',
        'enabled': True
    },
    {
        'url': 'https://feeds.feedburner.com/people/rss',
        'name': '人民网',
        'category': '综合',
        'language': 'zh',
        'enabled': False  # 示例，暂不启用
    },
    {
        'url': 'https://finance.sina.com.cn/roll/index.xml',
        'name': '新浪财经',
        'category': '财经',
        'language': 'zh',
        'enabled': False  # 示例，暂不启用
    }
]

# 抓取配置
FETCH_CONFIG = {
    'fetch_interval_hours': 1,        # 抓取间隔（小时）
    'max_news_per_fetch': 200,        # 每次抓取的最大新闻数量
    'retry_attempts': 3,              # 失败重试次数
    'request_timeout': 30,            # 请求超时时间（秒）
    'delay_between_requests': 2,      # 请求间延迟（秒）
}

# 数据库配置
DATABASE_CONFIG = {
    'mysql_url': 'mysql+pymysql://root:123456@localhost:3306/chat_robot',
    'pool_size': 10,
    'max_overflow': 20,
}

# Agent配置
AGENT_CONFIG = {
    'news_history_hours': 24,         # Agent分析的新闻时间范围
    'max_news_for_analysis': 50,      # 供Agent分析的最大新闻数量
    'title_matching_threshold': 0.7,  # 标题匹配置信度阈值
}

# 日志配置
LOGGING_CONFIG = {
    'level': 'INFO',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'file_path': 'logs/news_parser.log',
    'max_file_size': 10 * 1024 * 1024,  # 10MB
    'backup_count': 5,
}

def get_enabled_sources():
    """获取启用的RSS源"""
    return [source for source in RSS_SOURCES if source.get('enabled', False)]

def get_source_urls():
    """获取所有启用的RSS源URL"""
    return [source['url'] for source in get_enabled_sources()]

def get_source_names():
    """获取所有启用的RSS源名称"""
    return [source['name'] for source in get_enabled_sources()]