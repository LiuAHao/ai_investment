#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
会话服务
管理 V2 会话生命周期
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class SessionService:
    """会话服务"""

    @staticmethod
    def create_session(user_id: int, query: str) -> str:
        """创建新会话"""
        session_id = str(uuid.uuid4())

        try:
            from models import SessionLocal
            from models.database import AnalysisSession

            db = SessionLocal()
            try:
                session = AnalysisSession(
                    user_id=user_id,
                    session_id=session_id,
                    symbol="",
                    query=query,
                    status="pending",
                    progress=0,
                )
                db.add(session)
                db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.warning("创建会话记录失败: %s", e)

        return session_id

    @staticmethod
    def update_session_status(
        session_id: str,
        status: str,
        progress: int = 0,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        """更新会话状态"""
        try:
            import json
            from models import SessionLocal
            from models.database import AnalysisSession

            db = SessionLocal()
            try:
                session = db.query(AnalysisSession).filter_by(session_id=session_id).first()
                if session:
                    session.status = status
                    session.progress = progress
                    if result:
                        session.result_summary = json.dumps(result, ensure_ascii=False, default=str)
                    if error:
                        session.error_message = error
                    db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.warning("更新会话状态失败: %s", e)

    @staticmethod
    def get_session(session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话信息"""
        try:
            from models import SessionLocal
            from models.database import AnalysisSession

            db = SessionLocal()
            try:
                session = db.query(AnalysisSession).filter_by(session_id=session_id).first()
                if session:
                    return {
                        "session_id": session.session_id,
                        "user_id": session.user_id,
                        "status": session.status,
                        "progress": session.progress,
                        "query": session.query,
                    }
            finally:
                db.close()
        except Exception as e:
            logger.warning("获取会话失败: %s", e)
        return None
