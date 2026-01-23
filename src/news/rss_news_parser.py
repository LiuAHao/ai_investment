#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
RSS新闻解析器
用于从RSS源获取新闻信息并存储到数据库中
"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
import re
from typing import List, Dict, Optional, Tuple
import logging
from dataclasses import dataclass
import time
from urllib.parse import urljoin, urlparse
import hashlib

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
    content_hash: str = None

    def __post_init__(self):
        """生成内容哈希用于去重"""
        if self.content_hash is None:
            content = f"{self.title}{self.link}{self.pub_date.isoformat()}"
            self.content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()


class DatabaseManager:
    """数据库管理器"""

    def __init__(self, mysql_url: str):
        self.mysql_url = mysql_url
        self.conn = None
        self._connect()

    def _connect(self):
        """连接数据库"""
        try:
            import pymysql
            from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Index
            from sqlalchemy.ext.declarative import declarative_base
            from sqlalchemy.orm import sessionmaker

            # 创建数据库引擎
            self.engine = create_engine(self.mysql_url, echo=False)
            self.SessionLocal = sessionmaker(bind=self.engine)
            Base = declarative_base()

            # 定义新闻表结构
            class NewsTable(Base):
                __tablename__ = 'news_items'

                id = Column(Integer, primary_key=True, autoincrement=True)
                title = Column(String(500), nullable=False, comment='新闻标题')
                link = Column(String(255), unique=True, nullable=False, comment='新闻链接')
                description = Column(Text, comment='新闻描述')
                pub_date = Column(DateTime, nullable=False, comment='发布时间')
                source = Column(String(100), nullable=False, comment='新闻源')
                content_hash = Column(String(32), unique=True, nullable=False, comment='内容哈希')
                created_at = Column(DateTime, default=datetime.now(timezone.utc), comment='创建时间')
                updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc), comment='更新时间')

                # 创建索引
                __table_args__ = (
                    Index('idx_source_pub_date', 'source', 'pub_date'),
                    Index('idx_content_hash', 'content_hash'),
                    Index('idx_pub_date', 'pub_date'),
                )

            self.NewsTable = NewsTable
            Base.metadata.create_all(bind=self.engine)
            logger.info("数据库连接成功，表结构已创建")

        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            raise

    def save_news_items(self, news_items: List[NewsItem]) -> Tuple[int, int]:
        """
        保存新闻条目到数据库
        返回: (成功保存数量, 跳过数量)
        """
        if not news_items:
            return 0, 0

        session = self.SessionLocal()
        saved_count = 0
        skipped_count = 0

        try:
            for item in news_items:
                # 检查是否已存在
                existing = session.query(self.NewsTable).filter(
                    self.NewsTable.content_hash == item.content_hash
                ).first()

                if existing:
                    skipped_count += 1
                    logger.debug(f"新闻已存在，跳过: {item.title[:50]}...")
                    continue

                # 创建新记录
                news_record = self.NewsTable(
                    title=item.title,
                    link=item.link,
                    description=item.description,
                    pub_date=item.pub_date,
                    source=item.source,
                    content_hash=item.content_hash
                )

                session.add(news_record)
                saved_count += 1
                logger.debug(f"保存新闻: {item.title[:50]}...")

            session.commit()
            logger.info(f"成功保存 {saved_count} 条新闻，跳过 {skipped_count} 条重复新闻")

        except Exception as e:
            session.rollback()
            logger.error(f"保存新闻失败: {e}")
            raise
        finally:
            session.close()

        return saved_count, skipped_count

    def get_news_by_titles(self, titles: List[str], limit: int = 50) -> List[Dict]:
        """根据标题列表获取新闻详细信息"""
        session = self.SessionLocal()

        try:
            # 构建查询条件
            or_conditions = []
            for title in titles:
                # 使用模糊匹配找到相关标题
                or_conditions.append(self.NewsTable.title.like(f"%{title}%"))

            # 如果有查询条件
            if or_conditions:
                from sqlalchemy import or_
                query = session.query(self.NewsTable).filter(
                    or_(*or_conditions)
                ).order_by(self.NewsTable.pub_date.desc()).limit(limit)
            else:
                # 如果没有条件，返回最新的新闻
                query = session.query(self.NewsTable).order_by(
                    self.NewsTable.pub_date.desc()
                ).limit(limit)

            news_items = query.all()

            result = []
            for item in news_items:
                result.append({
                    'id': item.id,
                    'title': item.title,
                    'link': item.link,
                    'description': item.description,
                    'pub_date': item.pub_date,
                    'source': item.source
                })

            return result

        except Exception as e:
            logger.error(f"查询新闻失败: {e}")
            return []
        finally:
            session.close()

    def get_recent_news(self, hours: int = 24, limit: int = 100) -> List[Dict]:
        """获取最近N小时的新闻标题列表"""
        session = self.SessionLocal()

        try:
            from datetime import timedelta
            since_time = datetime.now(timezone.utc) - timedelta(hours=hours)

            query = session.query(self.NewsTable).filter(
                self.NewsTable.pub_date >= since_time
            ).order_by(self.NewsTable.pub_date.desc()).limit(limit)

            news_items = query.all()

            result = []
            for item in news_items:
                result.append({
                    'title': item.title,
                    'link': item.link,
                    'pub_date': item.pub_date,
                    'source': item.source
                })

            return result

        except Exception as e:
            logger.error(f"查询最近新闻失败: {e}")
            return []
        finally:
            session.close()

    def close(self):
        """关闭数据库连接"""
        if hasattr(self, 'engine'):
            self.engine.dispose()


class RSSNewsParser:
    """RSS新闻解析器"""

    def __init__(self, database_url: str = None):
        """
        初始化RSS解析器

        Args:
            database_url: 数据库连接URL，如果为None则不使用数据库
        """
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

        # 初始化数据库管理器
        if database_url:
            self.db_manager = DatabaseManager(database_url)
        else:
            self.db_manager = None

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

    def fetch_and_store_news(self, rss_urls: List[str], source_names: List[str] = None) -> Dict[str, Tuple[int, int]]:
        """
        抓取并存储新闻

        Args:
            rss_urls: RSS订阅地址列表
            source_names: 对应的新闻源名称列表

        Returns:
            每个源的保存结果字典: {source_name: (saved_count, skipped_count)}
        """
        if not self.db_manager:
            logger.error("数据库管理器未初始化，无法存储新闻")
            return {}

        results = {}

        for i, rss_url in enumerate(rss_urls):
            source_name = source_names[i] if source_names and i < len(source_names) else None

            try:
                # 解析RSS
                news_items = self.parse_rss_feed(rss_url, source_name)

                if not news_items:
                    results[source_name or rss_url] = (0, 0)
                    continue

                # 存储到数据库
                saved_count, skipped_count = self.db_manager.save_news_items(news_items)
                results[source_name or rss_url] = (saved_count, skipped_count)

                # 添加延迟避免频繁请求
                time.sleep(1)

            except Exception as e:
                logger.error(f"处理RSS源 {rss_url} 时出错: {e}")
                results[source_name or rss_url] = (0, 0)

        return results

    def get_news_for_agent(self, hours: int = 24) -> List[Dict]:
        """
        获取新闻标题列表供Agent分析

        Args:
            hours: 获取最近N小时的新闻

        Returns:
            包含标题、链接、发布时间和来源的字典列表
        """
        if not self.db_manager:
            logger.error("数据库管理器未初始化，无法获取新闻")
            return []

        return self.db_manager.get_recent_news(hours=hours)

    def get_news_details(self, titles: List[str], limit: int = 50) -> List[Dict]:
        """
        根据标题获取新闻详细信息

        Args:
            titles: 要获取的新闻标题列表
            limit: 最大返回数量

        Returns:
            包含完整新闻信息的字典列表
        """
        if not self.db_manager:
            logger.error("数据库管理器未初始化，无法获取新闻详情")
            return []

        return self.db_manager.get_news_by_titles(titles, limit=limit)

    def close(self):
        """关闭解析器"""
        if self.db_manager:
            self.db_manager.close()
        self.session.close()


def main():
    """主函数示例"""
    # 数据库配置（从环境变量或配置文件获取）
    import os
    mysql_url = os.getenv('MYSQL_URL', 'mysql+pymysql://root:123456@localhost:3306/chat_robot')

    # RSS源配置
    rss_sources = [
        ('https://plink.anyfeeder.com/jingjiribao', '经济日报'),
        # 可以添加更多RSS源
        # ('https://example.com/rss', '示例新闻源'),
    ]

    urls = [source[0] for source in rss_sources]
    names = [source[1] for source in rss_sources]

    # 创建解析器实例
    parser = RSSNewsParser(mysql_url)

    try:
        # 抓取并存储新闻
        logger.info("开始抓取新闻...")
        results = parser.fetch_and_store_news(urls, names)

        # 输出结果
        for source, (saved, skipped) in results.items():
            logger.info(f"{source}: 保存 {saved} 条，跳过 {skipped} 条")

        # 获取最近的新闻标题供Agent分析
        logger.info("\n获取最近24小时的新闻标题:")
        recent_news = parser.get_news_for_agent(hours=24)

        for news in recent_news[:10]:  # 显示前10条
            logger.info(f"- {news['title']} ({news['source']})")

        # 模拟Agent选择重要新闻后获取详情
        if recent_news:
            important_titles = [recent_news[0]['title']]  # 假设Agent选择了第一条新闻
            logger.info(f"\n获取重要新闻详情: {important_titles[0]}")

            details = parser.get_news_details(important_titles)
            if details:
                detail = details[0]
                logger.info(f"标题: {detail['title']}")
                logger.info(f"链接: {detail['link']}")
                logger.info(f"发布时间: {detail['pub_date']}")
                logger.info(f"描述: {detail['description'][:200]}...")

    except Exception as e:
        logger.error(f"程序执行出错: {e}")

    finally:
        parser.close()


if __name__ == "__main__":
    main()