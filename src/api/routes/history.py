#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
会话历史路由
提供进程内会话的列表与详情（内存态，重启清空）。
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify

logger = logging.getLogger(__name__)

history_bp = Blueprint("history_routes", __name__)


@history_bp.route("/history", methods=["GET"])
def list_sessions():
    """列出会话列表（新→旧）"""
    from agents.memory import get_session_memory
    sessions = get_session_memory().list_sessions(limit=100)
    return jsonify({"sessions": sessions}), 200


@history_bp.route("/history/<session_id>", methods=["GET"])
def get_session_history(session_id: str):
    """获取会话详情（turns 列表）"""
    from agents.memory import get_session_memory
    turns = get_session_memory().get_history(session_id)
    if turns is None:
        return jsonify({"error": "会话不存在"}), 404
    return jsonify({"session_id": session_id, "turns": turns}), 200
