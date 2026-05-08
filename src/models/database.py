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


class ResearchContext(Base):
    """研究上下文表，支持连续追问"""

    __tablename__ = "research_contexts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    session_id = Column(String(100), nullable=False, index=True)
    current_assets_json = Column(Text)
    last_intent_json = Column(Text)
    last_answer = Column(Text)
    last_evidence_ids_json = Column(Text)
    key_assumptions_json = Column(Text)
    user_preferences_json = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserPreferences(Base):
    """用户偏好表"""

    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False, index=True)
    risk_preference = Column(String(20), default="balanced")  # conservative, balanced, aggressive
    default_horizon = Column(String(20), default="medium")  # short, medium, long
    preferred_markets_json = Column(Text)
    preferred_industries_json = Column(Text)
    answer_style = Column(String(20), default="standard")  # standard, detailed, concise
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EvidenceRecord(Base):
    """证据池表，保存 V2 工具结果提炼后的证据"""

    __tablename__ = "evidence_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    evidence_id = Column(String(100), unique=True, nullable=False, index=True)
    session_id = Column(String(100), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    asset_id = Column(String(100), nullable=True, index=True)
    evidence_type = Column(String(50), nullable=False, index=True)
    title = Column(String(255), nullable=False, default="")
    summary = Column(Text)
    raw_json = Column(Text)
    source = Column(String(100), nullable=False, default="")
    source_url = Column(Text)
    observed_at = Column(DateTime)
    confidence = Column(Float, default=1.0)
    importance = Column(Float, default=0.5)
    polarity = Column(String(20))
    limitations_json = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class EvalCase(Base):
    """评测用例表"""

    __tablename__ = "eval_cases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(String(100), unique=True, nullable=False, index=True)
    category = Column(String(50), nullable=False, index=True)
    query = Column(Text, nullable=False)
    chat_history_json = Column(Text)
    user_profile_json = Column(Text)
    expected_behavior_json = Column(Text)
    reference_answer = Column(Text)
    tags_json = Column(Text)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EvalRun(Base):
    """评测运行表"""

    __tablename__ = "eval_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(100), unique=True, nullable=False, index=True)
    model_name = Column(String(100))
    prompt_version = Column(String(50))
    code_version = Column(String(50))
    dataset_name = Column(String(100), nullable=False)
    status = Column(String(20), default="pending")  # pending, running, completed, failed
    total_cases = Column(Integer, default=0)
    passed_cases = Column(Integer, default=0)
    avg_score = Column(Float, default=0.0)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    summary_json = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class EvalScore(Base):
    """评测分数表"""

    __tablename__ = "eval_scores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(100), nullable=False, index=True)
    case_id = Column(String(100), nullable=False, index=True)
    rule_score = Column(Float, default=0.0)
    llm_score = Column(Float, default=0.0)
    faithfulness_score = Column(Float, default=0.0)
    risk_score = Column(Float, default=0.0)
    compliance_score = Column(Float, default=0.0)
    context_score = Column(Float, default=0.0)
    tool_selection_score = Column(Float, default=0.0)
    final_score = Column(Float, default=0.0)
    details_json = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class AgentTrace(Base):
    """Agent 执行轨迹表"""

    __tablename__ = "agent_traces"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(100), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    node_name = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False)
    input_summary = Column(Text)
    output_summary = Column(Text)
    latency_ms = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class ToolCallRecord(Base):
    """工具调用记录表"""

    __tablename__ = "tool_calls"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(100), nullable=False, index=True)
    tool_name = Column(String(100), nullable=False, index=True)
    params_json = Column(Text)
    status = Column(String(20), nullable=False)  # success, failed, skipped, partial
    result_summary = Column(Text)
    error = Column(Text)
    latency_ms = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class ModelCallRecord(Base):
    """模型调用记录表"""

    __tablename__ = "model_calls"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(100), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    node_name = Column(String(100), nullable=True, index=True)
    model_name = Column(String(100))
    prompt_version = Column(String(50))
    status = Column(String(20), nullable=False, default="completed")
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    latency_ms = Column(Integer, default=0)
    error = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
