#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
数据库模型
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Text,
    ForeignKey,
    Float,
    Boolean,
)
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class User(Base):
    """用户表"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    phone = Column(String(30), nullable=True, index=True)
    password_hash = Column(String(255), nullable=False)
    nickname = Column(String(50), nullable=False)
    user_tier = Column(String(20), nullable=False, default="free")  # free / pro / premium
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)


class ChatHistory(Base):
    """聊天历史表"""

    __tablename__ = "chat_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    session_id = Column(String(100), nullable=False, index=True)


class AnalysisSession(Base):
    """分析会话表"""

    __tablename__ = "analysis_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    session_id = Column(String(100), unique=True, nullable=False, index=True)
    symbol = Column(String(20), nullable=False)
    query = Column(Text, nullable=False)
    status = Column(
        String(20), nullable=False, default="pending"
    )  # pending, processing, completed, failed
    progress = Column(Integer, default=0)
    result_summary = Column(Text)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AgentLog(Base):
    """Agent执行日志表"""

    __tablename__ = "agent_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(100), nullable=False, index=True)
    agent_name = Column(String(50), nullable=False)
    step_name = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False)  # pending, active, completed, failed
    log_message = Column(Text)
    progress_pct = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
