#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
新闻Agent集成模块
为投资分析Agent提供新闻信息支持
"""

from typing import List, Dict, Optional
from datetime import datetime, timedelta
import logging
from rss_news_parser import RSSNewsParser
from rss_config import AGENT_CONFIG, DATABASE_CONFIG

logger = logging.getLogger(__name__)


class NewsAgent:
    """新闻Agent - 为投资分析提供新闻信息支持"""

    def __init__(self):
        """初始化新闻Agent"""
        self.parser = RSSNewsParser(DATABASE_CONFIG['mysql_url'])
        logger.info("新闻Agent初始化完成")

    def get_recent_news_titles(self, hours: int = None) -> List[Dict]:
        """
        获取最近的新闻标题列表

        Args:
            hours: 获取最近N小时的新闻，默认使用配置文件中的值

        Returns:
            包含标题、链接、发布时间和来源的字典列表
        """
        if hours is None:
            hours = AGENT_CONFIG['news_history_hours']

        news_list = self.parser.get_news_for_agent(hours=hours)

        logger.info(f"获取到最近 {hours} 小时的 {len(news_list)} 条新闻")
        return news_list

    def analyze_news_relevance(self, keywords: List[str], news_titles: List[Dict]) -> List[Dict]:
        """
        根据关键词分析新闻相关性

        Args:
            keywords: 投资分析关键词列表
            news_titles: 新闻标题列表

        Returns:
            按相关性排序的新闻列表，包含相关性评分
        """
        relevant_news = []

        for news in news_titles:
            title = news.get('title', '').lower()
            score = 0

            # 计算关键词匹配分数
            for keyword in keywords:
                if keyword.lower() in title:
                    score += 1

            # 计算时效性分数（越新的新闻分数越高）
            pub_date = news.get('pub_date')
            if pub_date and isinstance(pub_date, datetime):
                hours_ago = (datetime.now(pub_date.tzinfo) - pub_date).total_seconds() / 3600
                time_score = max(0, 1 - hours_ago / 24)  # 24小时内的新闻有时间分数
                score += time_score

            if score > 0:
                news['relevance_score'] = score
                relevant_news.append(news)

        # 按相关性分数排序
        relevant_news.sort(key=lambda x: x['relevance_score'], reverse=True)

        logger.info(f"从 {len(news_titles)} 条新闻中找到 {len(relevant_news)} 条相关新闻")
        return relevant_news

    def get_news_details(self, titles: List[str], limit: int = None) -> List[Dict]:
        """
        根据标题获取新闻详细内容

        Args:
            titles: 要获取详细内容的新闻标题列表
            limit: 最大返回数量，默认使用配置文件中的值

        Returns:
            包含完整新闻信息的字典列表
        """
        if limit is None:
            limit = AGENT_CONFIG['max_news_for_analysis']

        return self.parser.get_news_details(titles, limit=limit)

    def get_financial_news_summary(self, stock_symbols: List[str] = None,
                                 sectors: List[str] = None) -> Dict:
        """
        获取财经新闻摘要

        Args:
            stock_symbols: 股票代码列表
            sectors: 行业板块列表

        Returns:
            包含相关新闻摘要的字典
        """
        # 构建搜索关键词
        keywords = []
        if stock_symbols:
            keywords.extend(stock_symbols)
        if sectors:
            keywords.extend(sectors)

        # 默认财经关键词
        financial_keywords = [
            '股市', '股票', '投资', '融资', '上市', '财报', '业绩', '并购',
            '经济', '金融', '银行', '保险', '基金', '证券', '期货'
        ]
        keywords.extend(financial_keywords)

        # 获取最近新闻
        recent_news = self.get_recent_news_titles()

        # 分析相关性
        relevant_news = self.analyze_news_relevance(keywords, recent_news)

        # 获取最重要的新闻详情
        important_titles = [news['title'] for news in relevant_news[:10]]
        detailed_news = self.get_news_details(important_titles)

        return {
            'total_news_count': len(recent_news),
            'relevant_news_count': len(relevant_news),
            'detailed_news': detailed_news,
            'summary_stats': {
                'by_source': self._count_by_source(relevant_news),
                'by_time': self._count_by_time(relevant_news)
            }
        }

    def _count_by_source(self, news_list: List[Dict]) -> Dict[str, int]:
        """按新闻源统计数量"""
        source_count = {}
        for news in news_list:
            source = news.get('source', '未知')
            source_count[source] = source_count.get(source, 0) + 1
        return source_count

    def _count_by_time(self, news_list: List[Dict]) -> Dict[str, int]:
        """按时间段统计数量"""
        time_count = {'0-6h': 0, '6-12h': 0, '12-24h': 0, '24h+': 0}
        now = datetime.now()

        for news in news_list:
            pub_date = news.get('pub_date')
            if not isinstance(pub_date, datetime):
                continue

            hours_ago = (now - pub_date.replace(tzinfo=None)).total_seconds() / 3600

            if hours_ago <= 6:
                time_count['0-6h'] += 1
            elif hours_ago <= 12:
                time_count['6-12h'] += 1
            elif hours_ago <= 24:
                time_count['12-24h'] += 1
            else:
                time_count['24h+'] += 1

        return time_count

    def get_market_sentiment_news(self) -> List[Dict]:
        """
        获取影响市场情绪的重要新闻

        Returns:
            可能影响市场情绪的重要新闻列表
        """
        # 市场情绪相关关键词
        sentiment_keywords = [
            '利好', '利空', '大涨', '大跌', '涨停', '跌停',
            '突破', '下跌', '上涨', '震荡', '调整',
            '政策', '央行', '利率', '通胀', '通缩',
            'GDP', '就业', '消费', '出口', '进口'
        ]

        recent_news = self.get_recent_news_titles()
        sentiment_news = self.analyze_news_relevance(sentiment_keywords, recent_news)

        # 获取高相关性新闻的详情
        important_titles = [news['title'] for news in sentiment_news[:5]]
        detailed_news = self.get_news_details(important_titles)

        return detailed_news

    def close(self):
        """关闭新闻Agent"""
        if self.parser:
            self.parser.close()
        logger.info("新闻Agent已关闭")


# 使用示例
def demo_usage():
    """使用示例"""
    agent = NewsAgent()

    try:
        # 1. 获取最近新闻标题
        print("=== 最近24小时新闻标题 ===")
        recent_news = agent.get_recent_news_titles()
        for i, news in enumerate(recent_news[:5]):
            print(f"{i+1}. {news['title']} ({news['source']})")

        # 2. 分析特定股票相关新闻
        print("\n=== 贵州茅台相关新闻 ===")
        stock_news = agent.analyze_news_relevance(['茅台', '白酒'], recent_news)
        for news in stock_news[:3]:
            print(f"- {news['title']} (相关度: {news['relevance_score']:.1f})")

        # 3. 获取新闻详情
        if stock_news:
            print(f"\n=== 新闻详情: {stock_news[0]['title']} ===")
            details = agent.get_news_details([stock_news[0]['title']])
            if details:
                print(f"描述: {details[0]['description'][:200]}...")
                print(f"链接: {details[0]['link']}")

        # 4. 获取财经新闻摘要
        print("\n=== 财经新闻摘要 ===")
        summary = agent.get_financial_news_summary(['A股', '沪深'])
        print(f"总新闻数: {summary['total_news_count']}")
        print(f"相关新闻数: {summary['relevant_news_count']}")
        print(f"新闻源分布: {summary['summary_stats']['by_source']}")

    finally:
        agent.close()


if __name__ == "__main__":
    demo_usage()