#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
数据库初始化
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import QueuePool, StaticPool
from models.database import Base
import os
from contextlib import contextmanager

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///ai_investment.db")

# 根据数据库类型配置连接池
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    engine = create_engine(
        DATABASE_URL,
        echo=False,
        pool_size=10,
        max_overflow=20,
        pool_timeout=30,
        pool_recycle=3600,
        pool_pre_ping=True,
    )

# 使用 scoped_session 支持多线程安全
SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))


def init_db():
    """初始化数据库表"""
    Base.metadata.create_all(bind=engine)


@contextmanager
def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
