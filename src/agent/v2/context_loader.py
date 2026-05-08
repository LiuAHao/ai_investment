#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
上下文加载节点
加载用户信息、聊天历史、风险偏好
"""

from __future__ import annotations

import logging
import json
from typing import Any, Dict, Optional

from agent.v2.state import Asset, IntentResult, InvestmentState, ResearchContext

logger = logging.getLogger(__name__)


def load_context(state: InvestmentState) -> Dict[str, Any]:
    """
    加载上下文信息
    
    职责：
    - 加载用户信息
    - 加载当前 session 的聊天历史
    - 加载用户风险偏好
    """
    logger.info("load_context: 加载上下文, session_id=%s", state.session_id)
    
    chat_history = []
    user_profile = dict(state.user_profile or {})
    research_context = None

    try:
        from models import SessionLocal, init_db
        from models.database import ChatHistory, User, UserPreferences

        init_db()
        db = SessionLocal()
        try:
            user = (
                db.query(User.id, User.username, User.nickname)
                .filter(User.id == state.user_id)
                .first()
            )
            if user:
                user_profile.update({
                    "id": user.id,
                    "username": user.username,
                    "nickname": user.nickname,
                    "user_tier": user_profile.get("user_tier", "free"),
                })

            prefs = db.query(UserPreferences).filter_by(user_id=state.user_id).first()
            if prefs:
                user_profile.setdefault("risk_preference", prefs.risk_preference)
                user_profile.setdefault("default_horizon", prefs.default_horizon)
                user_profile.setdefault("answer_style", prefs.answer_style)

            messages = (
                db.query(ChatHistory)
                .filter_by(session_id=state.session_id, user_id=state.user_id)
                .order_by(ChatHistory.created_at.desc())
                .limit(20)
                .all()
            )
            for msg in reversed(messages):
                chat_history.append({
                    "role": msg.role,
                    "content": msg.content,
                })
        finally:
            db.close()
    except Exception as e:
        logger.warning("加载上下文失败: %s", e)

    research_context = _load_research_context(state.user_id, state.session_id)

    trace = state.trace + [{
        "node": "load_context",
        "status": "completed",
        "input_summary": f"user_id={state.user_id}, session_id={state.session_id}",
        "output_summary": f"profile_loaded={bool(user_profile)}, history_count={len(chat_history)}, context_loaded={research_context is not None}",
        "latency_ms": 0,
    }]

    return {
        "chat_history": chat_history,
        "user_profile": user_profile,
        "research_context": research_context,
        "trace": trace,
    }


def _load_research_context(user_id: int, session_id: str) -> Optional[ResearchContext]:
    """加载上一轮研究上下文"""
    try:
        from models import SessionLocal, init_db
        from models.database import ResearchContext as ResearchContextDB

        init_db()
        db = SessionLocal()
        try:
            ctx = (
                db.query(ResearchContextDB)
                .filter_by(user_id=user_id, session_id=session_id)
                .first()
            )
            if not ctx:
                return None

            current_assets = [
                Asset.model_validate(item)
                for item in json.loads(ctx.current_assets_json or "[]")
            ]
            last_intent_data = json.loads(ctx.last_intent_json or "null")
            return ResearchContext(
                session_id=ctx.session_id,
                user_id=ctx.user_id,
                current_assets=current_assets,
                last_intent=IntentResult.model_validate(last_intent_data) if last_intent_data else None,
                last_answer=ctx.last_answer,
                last_evidence_ids=json.loads(ctx.last_evidence_ids_json or "[]"),
                key_assumptions=json.loads(ctx.key_assumptions_json or "[]"),
                user_preferences=json.loads(ctx.user_preferences_json or "{}"),
                created_at=ctx.created_at,
                updated_at=ctx.updated_at,
            )
        finally:
            db.close()
    except Exception as exc:
        logger.warning("加载研究上下文失败: %s", exc)
        return None
