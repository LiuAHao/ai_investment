#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
记忆管理节点
支持连续追问和上下文管理
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from agent.v2.state import Asset, EvidenceItem, IntentResult, InvestmentState, ResearchContext

logger = logging.getLogger(__name__)


def load_context(state: InvestmentState) -> Dict[str, Any]:
    """
    加载上下文
    
    职责：
    - 读取 research_contexts
    - 读取 chat_history
    - 读取 user_preferences
    - 读取上一轮 evidence
    """
    logger.info("load_context: 加载上下文, session_id=%s", state.session_id)

    chat_history = []
    user_profile = {}
    research_context = None

    try:
        from models import SessionLocal
        from models.database import User, ChatHistory

        db = SessionLocal()
        try:
            user = db.query(User).filter_by(id=state.user_id).first()
            if user:
                user_profile = {
                    "id": user.id,
                    "username": user.username,
                    "nickname": user.nickname,
                    "user_tier": getattr(user, "user_tier", "free"),
                    "risk_preference": getattr(user, "risk_preference", "balanced"),
                }

            messages = (
                db.query(ChatHistory)
                .filter_by(user_id=state.user_id, session_id=state.session_id)
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


def save_memory(state: InvestmentState) -> Dict[str, Any]:
    """
    保存记忆
    
    职责：
    - 保存对话到数据库
    - 更新研究上下文
    - 提取关键假设
    """
    logger.info("save_memory: 保存记忆")

    try:
        from models import SessionLocal, init_db
        from models.database import ChatHistory, AnalysisSession

        init_db()
        db = SessionLocal()
        try:
            user_msg = ChatHistory(
                user_id=state.user_id,
                session_id=state.session_id,
                role="user",
                content=state.query,
            )
            db.add(user_msg)

            answer = state.final_answer or state.draft_answer or ""
            assistant_msg = ChatHistory(
                user_id=state.user_id,
                session_id=state.session_id,
                role="assistant",
                content=answer,
            )
            db.add(assistant_msg)

            session = db.query(AnalysisSession).filter_by(session_id=state.session_id).first()
            if session:
                session.status = "completed"
                session.result_summary = json.dumps({
                    "final_answer": answer,
                    "assets": [a.model_dump() for a in state.assets],
                    "degraded": state.degraded,
                }, ensure_ascii=False, default=str)

            db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.warning("保存对话失败: %s", e)

    _save_evidence_items(state)
    _save_research_context(state)

    trace = state.trace + [{
        "node": "save_memory",
        "status": "completed",
        "input_summary": f"session_id={state.session_id}",
        "output_summary": "memory saved",
        "latency_ms": 0,
    }]

    return {
        "trace": trace,
    }


def finalize_answer(state: InvestmentState) -> Dict[str, Any]:
    """
    最终化答案
    
    职责：
    - 生成用户可读答案
    - 保存结构化答案
    - 更新任务状态
    """
    logger.info("finalize_answer: 最终化答案")

    final_answer = state.final_answer or state.draft_answer or "抱歉，无法生成分析结果。"

    trace = state.trace + [{
        "node": "finalize_answer",
        "status": "completed",
        "input_summary": f"draft_length={len(state.draft_answer or '')}",
        "output_summary": f"final_length={len(final_answer)}",
        "latency_ms": 0,
    }]

    return {
        "final_answer": final_answer,
        "trace": trace,
    }


def _load_research_context(user_id: int, session_id: str) -> Optional[ResearchContext]:
    """加载研究上下文"""
    try:
        from models import SessionLocal, init_db
        from models.database import ResearchContext as ResearchContextDB

        init_db()
        db = SessionLocal()
        try:
            ctx = db.query(ResearchContextDB).filter_by(
                user_id=user_id, session_id=session_id
            ).first()
            
            if ctx:
                return ResearchContext(
                    session_id=ctx.session_id,
                    user_id=ctx.user_id,
                    current_assets=[
                        Asset.model_validate(item)
                        for item in json.loads(ctx.current_assets_json or "[]")
                    ],
                    last_intent=IntentResult.model_validate(json.loads(ctx.last_intent_json)) if ctx.last_intent_json else None,
                    last_answer=ctx.last_answer,
                    last_evidence_ids=json.loads(ctx.last_evidence_ids_json) if ctx.last_evidence_ids_json else [],
                    key_assumptions=json.loads(ctx.key_assumptions_json) if ctx.key_assumptions_json else [],
                    user_preferences=json.loads(ctx.user_preferences_json) if ctx.user_preferences_json else {},
                    created_at=ctx.created_at,
                    updated_at=ctx.updated_at,
                )
        finally:
            db.close()
    except Exception as e:
        logger.warning("加载研究上下文失败: %s", e)
    
    return None


def _save_research_context(state: InvestmentState) -> None:
    """保存研究上下文"""
    try:
        from models import SessionLocal, init_db
        from models.database import ResearchContext as ResearchContextDB

        init_db()
        assumptions = _extract_key_assumptions(state)

        db = SessionLocal()
        try:
            existing = db.query(ResearchContextDB).filter_by(
                user_id=state.user_id, session_id=state.session_id
            ).first()

            if existing:
                existing.current_assets_json = json.dumps([a.model_dump() for a in state.assets], default=str)
                existing.last_intent_json = json.dumps(state.intent.model_dump() if state.intent else None, default=str)
                existing.last_answer = state.final_answer or state.draft_answer
                existing.last_evidence_ids_json = json.dumps([e.evidence_id for e in state.evidence_items[:20]])
                existing.key_assumptions_json = json.dumps(assumptions, default=str)
                existing.updated_at = datetime.now()
            else:
                ctx = ResearchContextDB(
                    user_id=state.user_id,
                    session_id=state.session_id,
                    current_assets_json=json.dumps([a.model_dump() for a in state.assets], default=str),
                    last_intent_json=json.dumps(state.intent.model_dump() if state.intent else None, default=str),
                    last_answer=state.final_answer or state.draft_answer,
                    last_evidence_ids_json=json.dumps([e.evidence_id for e in state.evidence_items[:20]]),
                    key_assumptions_json=json.dumps(assumptions, default=str),
                    user_preferences_json=json.dumps(state.user_profile, default=str),
                )
                db.add(ctx)

            db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.warning("保存研究上下文失败: %s", e)


def _save_evidence_items(state: InvestmentState) -> None:
    """保存证据池到数据库"""
    if not state.evidence_items:
        return

    try:
        from models import SessionLocal, init_db
        from models.database import EvidenceRecord

        init_db()
        db = SessionLocal()
        try:
            existing_ids = {
                row.evidence_id
                for row in db.query(EvidenceRecord.evidence_id)
                .filter(EvidenceRecord.evidence_id.in_([e.evidence_id for e in state.evidence_items]))
                .all()
            }
            for evidence in state.evidence_items:
                if evidence.evidence_id in existing_ids:
                    continue
                db.add(_build_evidence_record(state, evidence))
            db.commit()
        finally:
            db.close()
    except Exception as exc:
        logger.warning("保存证据池失败: %s", exc)


def _build_evidence_record(state: InvestmentState, evidence: EvidenceItem):
    """构造数据库证据记录"""
    from models.database import EvidenceRecord

    return EvidenceRecord(
        evidence_id=evidence.evidence_id,
        session_id=state.session_id,
        user_id=state.user_id,
        asset_id=evidence.asset_id,
        evidence_type=evidence.evidence_type.value,
        title=evidence.title,
        summary=evidence.summary,
        raw_json=json.dumps(evidence.raw, ensure_ascii=False, default=str),
        source=evidence.source,
        source_url=evidence.source_url,
        observed_at=evidence.observed_at,
        confidence=evidence.confidence,
        importance=evidence.importance,
        polarity=evidence.polarity.value if evidence.polarity else None,
        limitations_json=json.dumps(evidence.limitations, ensure_ascii=False, default=str),
    )


def _extract_key_assumptions(state: InvestmentState) -> List[Dict[str, Any]]:
    """提取关键假设"""
    assumptions = []
    
    for asset in state.assets[:3]:
        asset_evidence = [e for e in state.evidence_items if e.asset_id == asset.asset_id]
        
        if asset_evidence:
            assumption = {
                "asset_id": asset.asset_id,
                "assumptions": [],
            }
            
            market_data = [e for e in asset_evidence if e.evidence_type.value == "market_data"]
            if market_data:
                assumption["assumptions"].append("基于近期市场数据分析")
            
            news = [e for e in asset_evidence if e.evidence_type.value == "news"]
            if news:
                assumption["assumptions"].append("考虑了近期新闻事件影响")
            
            if assumption["assumptions"]:
                assumptions.append(assumption)
    
    return assumptions
