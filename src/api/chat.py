#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
聊天路由
"""

from flask import Blueprint, request, jsonify
from models.database import ChatHistory
from models import get_db
from api.auth import get_current_user
from agent.master_agent import MasterAgent
from utils.quota_manager import QuotaManager

chat_bp = Blueprint("chat", __name__)

master_agent = MasterAgent()
quota_manager = QuotaManager()


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

            sessions_data = []
            for session in sessions:
                first_user_message = (
                    db.query(ChatHistory)
                    .filter_by(
                        user_id=user.id,
                        session_id=session.session_id,
                        role="user",
                    )
                    .order_by(ChatHistory.created_at.asc())
                    .first()
                )
                first_message = first_user_message or (
                    db.query(ChatHistory)
                    .filter_by(user_id=user.id, session_id=session.session_id)
                    .order_by(ChatHistory.created_at.asc())
                    .first()
                )

                sessions_data.append(
                    {
                        "session_id": session.session_id,
                        "query": first_message.content if first_message else "",
                        "created_at": first_message.created_at.isoformat()
                        if first_message and first_message.created_at
                        else None,
                        "last_message_time": session.last_message_time.isoformat()
                        if session.last_message_time
                        else None,
                    }
                )

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


@chat_bp.route("/ask", methods=["POST"])
def ask():
    """简短问答（按需调用工具）"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "未授权"}), 401

    data = request.get_json() or {}
    content = data.get("content")
    session_id = data.get("session_id", "default")
    preferences = data.get("preferences")

    if not content:
        return jsonify({"error": "消息内容不能为空"}), 400

    # 配额检查
    user_tier = getattr(user, "user_tier", "free") or "free"
    allowed, msg = quota_manager.check_and_consume(user.id, "chat_per_day", user_tier)
    if not allowed:
        return jsonify({"error": msg}), 429

    with get_db() as db:
        try:
            user_chat = ChatHistory(
                user_id=user.id, role="user", content=content, session_id=session_id
            )
            db.add(user_chat)
            db.commit()

            workflow_result = master_agent.execute_phase2(
                user_query=content,
                preferences=preferences,
            )
            reply_text = workflow_result.get("recommendation", "")

            assistant_chat = ChatHistory(
                user_id=user.id,
                role="assistant",
                content=reply_text,
                session_id=session_id,
            )
            db.add(assistant_chat)
            db.commit()

            return jsonify(
                {
                    "message": "回答完成",
                    "reply": reply_text,
                    "session_id": session_id,
                }
            ), 200
        except Exception as e:
            db.rollback()
            return jsonify({"error": f"问答失败: {str(e)}"}), 500
