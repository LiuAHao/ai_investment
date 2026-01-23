#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
RSS新闻解析器
用于从RSS源获取新闻信息并返回关键标题
"""

import logging
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional
from urllib.parse import urlparse

import requests

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class NewsItem:
    """新闻项数据类"""
    title: str
    link: str
    description: str
    pub_date: datetime
    source: str


DEFAULT_SOURCES = [
    ("https://plink.anyfeeder.com/fortunechina", "财富中文网"),
    ("https://plink.anyfeeder.com/jingjiribao", "经济日报"),
]


class RSSNewsParser:
    """RSS新闻解析器（内部使用）"""

    def __init__(self, default_sources: Optional[List[tuple]] = None):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

        self.default_sources = default_sources or list(DEFAULT_SOURCES)

        logger.info("RSS新闻解析器初始化完成")

    def clean_html_tags(self, text: str) -> str:
        """清理HTML标签"""
        if not text:
            return ""

        # 移除HTML标签但保留内容
        # 先处理CDATA
        text = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', text, flags=re.DOTALL)

        # 移除HTML标签
        text = re.sub(r'<[^>]+>', '', text)

        # 清理多余空白
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    def parse_datetime(self, date_str: str) -> datetime:
        """解析日期时间字符串"""
        if not date_str:
            return datetime.now(timezone.utc)

        # 尝试不同的日期格式
        formats = [
            '%a, %d %b %Y %H:%M:%S %z',  # RFC 2822
            '%a, %d %b %Y %H:%M:%S %Z',  # RFC 2822 with timezone name
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%d',
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                # 如果没有时区信息，添加UTC时区
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue

        # 如果都无法解析，使用当前时间
        logger.warning(f"无法解析日期字符串: {date_str}")
        return datetime.now(timezone.utc)

    def parse_rss_feed(self, rss_url: str, source_name: str = None) -> List[NewsItem]:
        """
        解析RSS订阅源

        Args:
            rss_url: RSS订阅地址
            source_name: 新闻源名称，如果为None则从URL中提取

        Returns:
            NewsItem列表
        """
        if not source_name:
            # 从URL中提取域名作为源名称
            parsed_url = urlparse(rss_url)
            source_name = parsed_url.netloc

        logger.info(f"开始解析RSS源: {rss_url}")

        try:
            # 获取RSS内容
            response = self.session.get(rss_url, timeout=30)
            response.raise_for_status()

            # 解析XML
            root = ET.fromstring(response.content)

            news_items = []

            # 处理不同的RSS格式
            if root.tag == 'rss':
                # 标准RSS格式
                channel = root.find('channel')
                items = channel.findall('item') if channel else []
            elif root.tag.endswith('feed'):
                # Atom格式
                items = root.findall('entry')
            else:
                # 直接在根节点下找item
                items = root.findall('item')

            for item in items:
                try:
                    # 提取标题
                    title_elem = item.find('title')
                    title = self.clean_html_tags(title_elem.text if title_elem is not None else "")

                    # 提取链接
                    link_elem = item.find('link')
                    link = ""
                    if link_elem is not None:
                        link = link_elem.text if link_elem.text else link_elem.get('href', "")

                    # 提取描述
                    description_elem = item.find('description')
                    description = self.clean_html_tags(
                        description_elem.text if description_elem is not None else ""
                    )

                    # 提取发布日期
                    pub_date_elem = item.find('pubDate')
                    pub_date = self.parse_datetime(
                        pub_date_elem.text if pub_date_elem is not None else ""
                    )
                    if pub_date_elem is None:
                        updated_elem = item.find('updated')
                        if updated_elem is not None:
                            pub_date = self.parse_datetime(updated_elem.text or "")

                    # 创建新闻项
                    news_item = NewsItem(
                        title=title,
                        link=link,
                        description=description,
                        pub_date=pub_date,
                        source=source_name
                    )

                    news_items.append(news_item)

                except Exception as e:
                    logger.warning(f"解析单个新闻项时出错: {e}")
                    continue

            logger.info(f"成功解析 {len(news_items)} 条新闻")
            return news_items

        except requests.RequestException as e:
            logger.error(f"获取RSS内容失败: {e}")
            return []
        except ET.ParseError as e:
            logger.error(f"解析XML内容失败: {e}")
            return []
        except Exception as e:
            logger.error(f"解析RSS源时出错: {e}")
            return []

    def fetch_titles(self, rss_urls: Optional[List[str]] = None, source_names: Optional[List[str]] = None, limit: int = 100) -> List[str]:
        """
        拉取多个 RSS 源并返回标题列表

        Args:
            rss_urls: RSS订阅地址列表；不传则使用默认数据源
            source_names: 对应的新闻源名称列表
            limit: 最多返回标题数量

        Returns:
            标题列表
        """
        titles: List[str] = []

        sources = rss_urls or [source[0] for source in self.default_sources]
        names = source_names or [source[1] for source in self.default_sources]

        for i, rss_url in enumerate(sources):
            source_name = names[i] if names and i < len(names) else None
            try:
                news_items = self.parse_rss_feed(rss_url, source_name)
                for item in news_items:
                    if item.title:
                        titles.append(item.title)
                    if len(titles) >= limit:
                        return titles[:limit]
                time.sleep(1)
            except Exception as e:
                logger.error(f"处理RSS源 {rss_url} 时出错: {e}")

        return titles

    def close(self):
        """关闭解析器"""
        self.session.close()


def get_news_titles(limit: int = 100, sources: Optional[List[tuple]] = None) -> List[str]:
    """
    对外接口：获取新闻标题列表

    Args:
        limit: 最多返回标题数量
        sources: 可选数据源列表，默认使用内置数据源

    Returns:
        标题列表
    """
    parser = RSSNewsParser(default_sources=sources or list(DEFAULT_SOURCES))
    try:
        return parser.fetch_titles(limit=limit)
    finally:
        parser.close()