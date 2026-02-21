#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Agent 工作流路由
"""

import os
import time
import hashlib
import threading
from flask import Blueprint, request, jsonify
from sqlalchemy.orm import Session
import uuid
from models.database import AnalysisSession, AgentLog
from models import get_db
from api.agent_executor import AgentWorkflowExecutor
from api.auth import get_current_user
from concurrent.futures import ThreadPoolExecutor

agent_bp = Blueprint("agent", __name__)

# ── 线程池限制 ──
MAX_WORKERS = int(os.getenv("AGENT_MAX_WORKERS", "10"))
_agent_thread_pool = ThreadPoolExecutor(max_workers=MAX_WORKERS)

# ── 重复任务检测 ──
_recent_tasks: dict = {}
_recent_tasks_lock = threading.Lock()
_DEDUP_WINDOW = 30  # 30秒内相同请求视为重复

# ── 输入限制 ──
MAX_QUERY_LENGTH = 2000
MAX_SYMBOL_LENGTH = 20


def _is_duplicate_task(user_id: int, symbol: str, query: str) -> tuple:
    """检测重复任务，防止用户快速连续提交"""
    task_key = hashlib.md5(f"{user_id}:{symbol}:{query}".encode()).hexdigest()
    now = time.time()
    with _recent_tasks_lock:
        # 清理过期记录
        expired = [k for k, v in _recent_tasks.items() if now - v > _DEDUP_WINDOW]
        for k in expired:
            del _recent_tasks[k]
        if task_key in _recent_tasks:
            return True, int(_DEDUP_WINDOW - (now - _recent_tasks[task_key]))
        _recent_tasks[task_key] = now
        return False, 0


def _count_active_tasks() -> int:
    """统计当前正在处理的任务数"""
    return len([e for e in AgentWorkflowExecutor._executors.values()
                if e.status == "processing"])


@agent_bp.route("/analyze", methods=["POST"])
def analyze():
    """启动分析工作流"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "未授权"}), 401

    data = request.get_json()
    symbol = data.get("symbol", "").strip()
    news_limit = data.get("news_limit", 20)
    preferences = data.get("preferences")
    user_query = data.get("query", "").strip() or f"分析股票 {symbol}"

    if not symbol:
        return jsonify({"error": "缺少股票代码"}), 400

    # ── 输入校验 ──
    if len(symbol) > MAX_SYMBOL_LENGTH:
        return jsonify({"error": "股票代码过长"}), 400
    if len(user_query) > MAX_QUERY_LENGTH:
        return jsonify({"error": f"查询内容过长，最多{MAX_QUERY_LENGTH}字符"}), 400

    # ── 配额检查 ──
    from utils.quota_manager import quota_manager
    user_tier = getattr(user, "user_tier", "free") or "free"
    allowed, quota_info = quota_manager.check_and_consume(user.id, "analysis_per_day", user_tier=user_tier)
    if not allowed:
        return jsonify({
            "error": "今日分析次数已用完",
            "quota": quota_info,
        }), 429

    # ── 重复任务检测 ──
    is_dup, retry_after = _is_duplicate_task(user.id, symbol, user_query)
    if is_dup:
        return jsonify({
            "error": "相同的分析请求过于频繁，请稍后再试",
            "retry_after": retry_after,
        }), 429

    # ── 系统容量检查 ──
    if _count_active_tasks() >= MAX_WORKERS:
        return jsonify({
            "error": "系统繁忙，请稍后再试",
        }), 503

    session_id = str(uuid.uuid4())

    with get_db() as db:
        try:
            analysis_session = AnalysisSession(
                user_id=user.id,
                session_id=session_id,
                symbol=symbol,
                query=user_query,
                status="pending",
                progress=0,
            )
            db.add(analysis_session)
            db.commit()

            executor = AgentWorkflowExecutor.get_executor(session_id)

            _agent_thread_pool.submit(
                executor.run_analysis, symbol, news_limit, preferences, user_query
            )

            return jsonify(
                {"message": "分析已启动", "session_id": session_id, "status": "processing"}
            ), 200

        except Exception as e:
            db.rollback()
            return jsonify({"error": f"启动失败: {str(e)}"}), 500


@agent_bp.route("/query", methods=["POST"])
def query():
    """启动查询工作流"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "未授权"}), 401

    data = request.get_json()
    user_query = data.get("query", "").strip()
    preferences = data.get("preferences")

    if not user_query:
        return jsonify({"error": "缺少查询内容"}), 400

    # ── 输入校验 ──
    if len(user_query) > MAX_QUERY_LENGTH:
        return jsonify({"error": f"查询内容过长，最多{MAX_QUERY_LENGTH}字符"}), 400

    # ── 配额检查 ──
    from utils.quota_manager import quota_manager
    user_tier = getattr(user, "user_tier", "free") or "free"
    allowed, quota_info = quota_manager.check_and_consume(user.id, "analysis_per_day", user_tier=user_tier)
    if not allowed:
        return jsonify({
            "error": "今日分析次数已用完",
            "quota": quota_info,
        }), 429

    # ── 重复任务检测 ──
    is_dup, retry_after = _is_duplicate_task(user.id, "", user_query)
    if is_dup:
        return jsonify({
            "error": "相同的查询请求过于频繁，请稍后再试",
            "retry_after": retry_after,
        }), 429

    # ── 系统容量检查 ──
    if _count_active_tasks() >= MAX_WORKERS:
        return jsonify({
            "error": "系统繁忙，请稍后再试",
        }), 503

    session_id = str(uuid.uuid4())

    with get_db() as db:
        try:
            analysis_session = AnalysisSession(
                user_id=user.id,
                session_id=session_id,
                symbol="",
                query=user_query,
                status="pending",
                progress=0,
            )
            db.add(analysis_session)
            db.commit()

            executor = AgentWorkflowExecutor.get_executor(session_id)

            _agent_thread_pool.submit(
                executor.run_query, user_query, preferences
            )

            return jsonify(
                {"message": "查询已启动", "session_id": session_id, "status": "processing"}
            ), 200

        except Exception as e:
            db.rollback()
            return jsonify({"error": f"启动失败: {str(e)}"}), 500


@agent_bp.route("/status/<session_id>", methods=["GET"])
def get_status(session_id: str):
    """获取分析状态"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "未授权"}), 401

    with get_db() as db:
        try:
            session = (
                db.query(AnalysisSession)
                .filter_by(session_id=session_id, user_id=user.id)
                .first()
            )
            if not session:
                return jsonify({"error": "会话不存在"}), 404

            logs = (
                db.query(AgentLog)
                .filter_by(session_id=session_id)
                .order_by(AgentLog.created_at)
                .all()
            )

            logs_data = [
                {
                    "agent": log.agent_name,
                    "step": log.step_name,
                    "text": log.log_message,
                    "status": log.status,
                    "progress": log.progress_pct,
                    "timestamp": log.created_at.isoformat() if log.created_at else None,
                }
                for log in logs
            ]

            result_payload = session.result_summary
            if isinstance(result_payload, str) and result_payload.strip().startswith(("{", "[")):
                try:
                    import json

                    result_payload = json.loads(result_payload)
                except Exception:
                    pass

            return jsonify(
                {
                    "session_id": session_id,
                    "status": session.status,
                    "progress": session.progress,
                    "logs": logs_data,
                    "result": result_payload,
                    "error": session.error_message,
                }
            ), 200

        except Exception as e:
            return jsonify({"error": f"获取状态失败: {str(e)}"}), 500


@agent_bp.route("/sessions", methods=["GET"])
def list_sessions():
    """获取用户分析会话列表"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "未授权"}), 401

    with get_db() as db:
        try:
            limit = request.args.get("limit", 20, type=int)
            offset = request.args.get("offset", 0, type=int)

            sessions = (
                db.query(AnalysisSession)
                .filter_by(user_id=user.id)
                .order_by(AnalysisSession.created_at.desc())
                .limit(limit)
                .offset(offset)
                .all()
            )

            sessions_data = [
                {
                    "session_id": s.session_id,
                    "symbol": s.symbol,
                    "query": s.query,
                    "status": s.status,
                    "progress": s.progress,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                }
                for s in sessions
            ]

            return jsonify({"sessions": sessions_data}), 200

        except Exception as e:
            return jsonify({"error": f"获取会话列表失败: {str(e)}"}), 500
