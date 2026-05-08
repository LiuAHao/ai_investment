#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
反馈服务
管理用户反馈和评测
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class FeedbackService:
    """反馈服务"""

    @staticmethod
    def save_feedback(
        session_id: str,
        user_id: int,
        rating: Optional[int] = None,
        comment: Optional[str] = None,
        feedback_type: str = "general",
    ) -> bool:
        """保存用户反馈"""
        try:
            from models import SessionLocal
            from models.database import AnalysisSession

            db = SessionLocal()
            try:
                session = db.query(AnalysisSession).filter_by(session_id=session_id).first()
                if session:
                    metadata = {}
                    if session.result_summary:
                        try:
                            metadata = json.loads(session.result_summary) if isinstance(session.result_summary, str) else {}
                        except Exception:
                            pass
                    
                    metadata["feedback"] = {
                        "rating": rating,
                        "comment": comment,
                        "type": feedback_type,
                    }
                    session.result_summary = json.dumps(metadata, ensure_ascii=False, default=str)
                    db.commit()
                    return True
            finally:
                db.close()
        except Exception as e:
            logger.warning("保存反馈失败: %s", e)
        return False

    @staticmethod
    def get_feedback_stats(user_id: int) -> Dict[str, Any]:
        """获取用户反馈统计"""
        try:
            from models import SessionLocal
            from models.database import AnalysisSession

            db = SessionLocal()
            try:
                sessions = db.query(AnalysisSession).filter_by(user_id=user_id).all()
                total = 0
                rated = 0
                total_rating = 0

                for session in sessions:
                    if session.result_summary:
                        try:
                            data = json.loads(session.result_summary) if isinstance(session.result_summary, str) else {}
                            feedback = data.get("feedback", {})
                            if feedback.get("rating"):
                                total += 1
                                rated += 1
                                total_rating += feedback["rating"]
                        except Exception:
                            pass

                return {
                    "total_sessions": len(sessions),
                    "rated_sessions": rated,
                    "average_rating": total_rating / rated if rated > 0 else 0,
                }
            finally:
                db.close()
        except Exception as e:
            logger.warning("获取反馈统计失败: %s", e)
        return {"total_sessions": 0, "rated_sessions": 0, "average_rating": 0}
