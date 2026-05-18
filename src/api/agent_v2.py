#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
V2 Agent API 蓝图
提供 V2 版本的查询和状态接口
"""

from __future__ import annotations

import logging
import os
from flask import Blueprint, jsonify, request

from api.auth import get_current_user
from agent.v2.schemas import QueryRequest
from services.session_service import SessionService
from services.task_service import TaskService

logger = logging.getLogger(__name__)

agent_v2_bp = Blueprint("agent_v2", __name__)

MAX_QUERY_LENGTH = 2000


def _normalize_preferences(preferences: dict | None) -> dict:
    preferences = preferences or {}
    debug_mode = preferences.get("debug_mode", preferences.get("debugMode", False))
    risk_preference = preferences.get("risk_preference", preferences.get("riskPref"))
    investment_horizon = preferences.get("investment_horizon", preferences.get("period"))
    return {
        "debug_mode": bool(debug_mode),
        "risk_preference": risk_preference,
        "investment_horizon": investment_horizon,
    }


@agent_v2_bp.route("/query", methods=["POST"])
def query():
    """
    V2 查询接口
    
    职责：
    - 校验用户身份
    - 校验 query 长度
    - 创建或复用 session_id
    - 初始化 V2 状态
    - 启动 V2 图执行
    - 返回 task_id 和 session_id
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "未授权"}), 401

    if not os.getenv("AGENT_V2_ENABLED", "false").lower() == "true":
        return jsonify({"error": "V2 功能未开启"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "缺少请求体"}), 400

    try:
        payload = QueryRequest.model_validate(data)
    except Exception as exc:
        return jsonify({"error": f"请求参数无效: {str(exc)}"}), 400

    query_text = payload.query.strip()
    session_id = payload.session_id
    preferences = _normalize_preferences(payload.preferences)

    if not query_text:
        return jsonify({"error": "缺少查询内容"}), 400

    if len(query_text) > MAX_QUERY_LENGTH:
        return jsonify({"error": f"查询内容过长，最多{MAX_QUERY_LENGTH}字符"}), 400

    try:
        if not session_id:
            session_id = SessionService.create_session(user.id, query_text)
        else:
            session = SessionService.get_session(session_id)
            if not session:
                return jsonify({"error": "会话不存在"}), 404
            if session.get("user_id") != user.id:
                return jsonify({"error": "无权访问该会话"}), 403

        from utils.quota_manager import quota_manager

        user_tier = getattr(user, "user_tier", "free") or "free"
        allowed, quota_info = quota_manager.check_and_consume(
            user.id,
            "analysis_per_day",
            user_tier=user_tier,
        )
        if not allowed:
            return jsonify({
                "error": "今日分析额度已用完",
                "quota": quota_info,
            }), 429

        task_id = TaskService.create_task(session_id, user.id)

        def execute_v2():
            from agent.v2.graph import run_v2_query

            chat_history = []
            user_profile = {
                "id": user.id,
                "username": user.username,
                "debug_mode": preferences.get("debug_mode", False),
                "risk_preference": preferences.get("risk_preference"),
                "investment_horizon": preferences.get("investment_horizon"),
                "preferences": preferences,
            }

            result = run_v2_query(
                session_id=session_id,
                user_id=user.id,
                query=query_text,
                chat_history=chat_history,
                user_profile=user_profile,
                task_id=task_id,
            )
            return result

        timeout_seconds = int(os.getenv("AGENT_V2_TOTAL_TIMEOUT", "120"))
        TaskService.submit_task(task_id, execute_v2, timeout_seconds=timeout_seconds)

        return jsonify({
            "task_id": task_id,
            "session_id": session_id,
            "status": "processing",
            "message": "查询已提交",
            "quota": quota_info,
        }), 200

    except Exception as e:
        logger.error("V2 查询启动失败: %s", e)
        return jsonify({"error": f"启动失败: {str(e)}"}), 500


@agent_v2_bp.route("/status/<task_id>", methods=["GET"])
def get_status(task_id: str):
    """
    任务状态接口
    
    职责：
    - 返回任务状态
    - 返回当前节点
    - 返回进度
    - 返回部分工具结果
    - 返回最终结果
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "未授权"}), 401

    task = TaskService.get_task(task_id)
    if not task:
        return jsonify({"error": "任务不存在"}), 404
    if task.user_id != user.id:
        return jsonify({"error": "无权访问该任务"}), 403

    response = {
        "task_id": task.task_id,
        "session_id": task.session_id,
        "status": task.status,
        "progress": task.progress,
        "current_node": task.current_node,
        "trace": task.trace,
    }

    if task.status == "completed" and task.result:
        response["result"] = task.result
    elif task.status in ("failed", "timeout"):
        response["error"] = task.error

    return jsonify(response), 200


@agent_v2_bp.route("/session/<session_id>", methods=["GET"])
def get_session(session_id: str):
    """获取会话详情"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "未授权"}), 401

    session = SessionService.get_session(session_id)
    if not session:
        return jsonify({"error": "会话不存在"}), 404

    if session.get("user_id") != user.id:
        return jsonify({"error": "无权访问"}), 403

    return jsonify(session), 200


@agent_v2_bp.route("/health", methods=["GET"])
def health():
    """V2 健康检查"""
    v2_enabled = os.getenv("AGENT_V2_ENABLED", "false").lower() == "true"
    return jsonify({
        "status": "ok",
        "v2_enabled": v2_enabled,
        "version": "2.0.0",
    }), 200
