#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
聊天路由
"""

from flask import Blueprint, request, jsonify
from sqlalchemy.orm import Session
from datetime import datetime
from models.database import ChatHistory
from models import get_db
from api.auth import get_current_user

chat_bp = Blueprint("chat", __name__)


@chat_bp.route("/send", methods=["POST"])
def send():
    """发送消息"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "未授权"}), 401

    data = request.get_json()
    content = data.get("content")
    session_id = data.get("session_id", "default")
    role = data.get("role", "user")

    if not content:
        return jsonify({"error": "消息内容不能为空"}), 400

    with get_db() as db:
        try:
            chat = ChatHistory(
                user_id=user.id, role=role, content=content, session_id=session_id
            )
            db.add(chat)
            db.commit()

            return jsonify(
                {
                    "message": "消息已发送",
                    "id": chat.id,
                    "created_at": chat.created_at.isoformat(),
                }
            ), 201

        except Exception as e:
            db.rollback()
            return jsonify({"error": f"发送失败: {str(e)}"}), 500


@chat_bp.route("/history", methods=["GET"])
def history():
    """获取聊天历史"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "未授权"}), 401

    session_id = request.args.get("session_id", "default")
    limit = request.args.get("limit", 50, type=int)
    offset = request.args.get("offset", 0, type=int)

    with get_db() as db:
        try:
            chats = (
                db.query(ChatHistory)
                .filter_by(user_id=user.id, session_id=session_id)
                .order_by(ChatHistory.created_at.asc())
                .limit(limit)
                .offset(offset)
                .all()
            )

            history_data = [
                {
                    "id": chat.id,
                    "role": chat.role,
                    "content": chat.content,
                    "created_at": chat.created_at.isoformat() if chat.created_at else None,
                }
                for chat in chats
            ]

            return jsonify(
                {
                    "history": history_data,
                    "count": len(history_data),
                    "session_id": session_id,
                }
            ), 200

        except Exception as e:
            return jsonify({"error": f"获取历史失败: {str(e)}"}), 500


@chat_bp.route("/sessions", methods=["GET"])
def sessions():
    """获取聊天会话列表"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "未授权"}), 401

    with get_db() as db:
        try:
            from sqlalchemy import func

            subquery = (
                db.query(
                    ChatHistory.session_id,
                    func.max(ChatHistory.created_at).label("last_message_time"),
                )
                .filter_by(user_id=user.id)
                .group_by(ChatHistory.session_id)
                .subquery()
            )

            sessions = (
                db.query(ChatHistory.session_id, subquery.c.last_message_time)
                .join(subquery, ChatHistory.session_id == subquery.c.session_id)
                .distinct()
                .order_by(subquery.c.last_message_time.desc())
                .limit(20)
                .all()
            )

            sessions_data = [
                {
                    "session_id": session.session_id,
                    "last_message_time": session.last_message_time.isoformat()
                    if session.last_message_time
                    else None,
                }
                for session in sessions
            ]

            return jsonify({"sessions": sessions_data}), 200

        except Exception as e:
            return jsonify({"error": f"获取会话列表失败: {str(e)}"}), 500


@chat_bp.route("/clear", methods=["DELETE"])
def clear():
    """清空聊天历史"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "未授权"}), 401

    session_id = request.args.get("session_id", "default")

    with get_db() as db:
        try:
            db.query(ChatHistory).filter_by(user_id=user.id, session_id=session_id).delete()

            db.commit()

            return jsonify({"message": "聊天历史已清空"}), 200

        except Exception as e:
            db.rollback()
            return jsonify({"error": f"清空失败: {str(e)}"}), 500
