#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
反馈 API
管理用户对分析结果的反馈
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request
from pydantic import BaseModel, Field

from api.auth import get_current_user

logger = logging.getLogger(__name__)

feedback_bp = Blueprint("feedback", __name__)


class FeedbackRequest(BaseModel):
    """反馈请求"""
    session_id: str
    task_id: Optional[str] = None
    rating: Optional[int] = Field(None, ge=1, le=5)
    feedback_type: str = "general"
    comment: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)


FEEDBACK_TYPES = [
    "useful",
    "inaccurate",
    "risk_insufficient",
    "not_specific",
    "data_issue",
    "other",
]


@feedback_bp.route("/feedback", methods=["POST"])
def submit_feedback():
    """
    提交反馈
    
    反馈类型：
    - useful: 有用
    - inaccurate: 不准确
    - risk_insufficient: 风险提示不足
    - not_specific: 不够具体
    - data_issue: 工具数据有问题
    - other: 其他反馈
    """
    user = get_current_user()
    if not user:
        return jsonify({"error": "未授权"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"error": "缺少请求体"}), 400

    try:
        feedback = FeedbackRequest(**data)
    except Exception as e:
        return jsonify({"error": f"参数错误: {str(e)}"}), 400

    if feedback.feedback_type not in FEEDBACK_TYPES:
        return jsonify({"error": f"无效的反馈类型，可选: {FEEDBACK_TYPES}"}), 400

    try:
        from models import SessionLocal
        from models.database import AnalysisSession

        db = SessionLocal()
        try:
            session = db.query(AnalysisSession).filter_by(
                session_id=feedback.session_id,
                user_id=user.id,
            ).first()

            if not session:
                return jsonify({"error": "会话不存在"}), 404

            result_summary = {}
            if session.result_summary:
                try:
                    result_summary = json.loads(session.result_summary) if isinstance(session.result_summary, str) else {}
                except Exception:
                    pass

            result_summary["feedback"] = {
                "rating": feedback.rating,
                "feedback_type": feedback.feedback_type,
                "comment": feedback.comment,
                "details": feedback.details,
                "submitted_at": datetime.now().isoformat(),
            }

            session.result_summary = json.dumps(result_summary, ensure_ascii=False, default=str)
            db.commit()

            return jsonify({
                "message": "反馈提交成功",
                "session_id": feedback.session_id,
                "feedback_type": feedback.feedback_type,
            }), 200
        finally:
            db.close()
    except Exception as e:
        logger.error("提交反馈失败: %s", e)
        return jsonify({"error": f"提交失败: {str(e)}"}), 500


@feedback_bp.route("/feedback/<session_id>", methods=["GET"])
def get_feedback(session_id: str):
    """获取反馈"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "未授权"}), 401

    try:
        from models import SessionLocal
        from models.database import AnalysisSession

        db = SessionLocal()
        try:
            session = db.query(AnalysisSession).filter_by(
                session_id=session_id,
                user_id=user.id,
            ).first()

            if not session:
                return jsonify({"error": "会话不存在"}), 404

            result_summary = {}
            if session.result_summary:
                try:
                    result_summary = json.loads(session.result_summary) if isinstance(session.result_summary, str) else {}
                except Exception:
                    pass

            feedback = result_summary.get("feedback")

            return jsonify({
                "session_id": session_id,
                "feedback": feedback,
            }), 200
        finally:
            db.close()
    except Exception as e:
        logger.error("获取反馈失败: %s", e)
        return jsonify({"error": f"获取失败: {str(e)}"}), 500
