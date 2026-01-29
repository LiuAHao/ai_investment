#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
数据库初始化
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.database import Base
import os
from contextlib import contextmanager

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///ai_investment.db")

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


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
