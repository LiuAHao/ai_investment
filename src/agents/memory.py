#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
会话记忆
进程内内存态会话管理（决策 #12：不落库，重启清空）。
"""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from agents.state import Asset, InvestmentAnswer, ResearchContext

logger = logging.getLogger(__name__)


class MemorySession:
    """单个内存会话"""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.turns: List[Dict[str, Any]] = []
        self.context: Optional[ResearchContext] = None
        self.last_answer: Optional[InvestmentAnswer] = None

    def add_turn(self, query: str, answer: InvestmentAnswer, agent_results: List[Dict[str, Any]]) -> None:
        self.turns.append({
            "query": query,
            "answer": answer.model_dump(),
            "agent_results": agent_results,
            "timestamp": datetime.now().isoformat(),
        })
        self.last_answer = answer
        self.updated_at = datetime.now()


class SessionMemory:
    """会话记忆管理器（进程内单例）"""

    def __init__(self):
        self._sessions: Dict[str, MemorySession] = {}
        self._lock = threading.Lock()

    def create_session(self) -> MemorySession:
        session_id = f"mem_{uuid.uuid4().hex[:12]}"
        with self._lock:
            session = MemorySession(session_id)
            self._sessions[session_id] = session
        logger.info("创建内存会话: %s", session_id)
        return session

    def get_session(self, session_id: str) -> Optional[MemorySession]:
        return self._sessions.get(session_id)

    def get_or_create(self, session_id: str) -> MemorySession:
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = MemorySession(session_id)
            return self._sessions[session_id]

    def list_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """列出全部会话（新→旧）"""
        sessions = sorted(
            self._sessions.values(),
            key=lambda s: s.updated_at,
            reverse=True,
        )
        return [
            {
                "session_id": s.session_id,
                "created_at": s.created_at.isoformat(),
                "updated_at": s.updated_at.isoformat(),
                "title": (s.turns[0]["query"][:30] if s.turns else "新对话"),
                "turn_count": len(s.turns),
            }
            for s in sessions[:limit]
        ]

    def get_history(self, session_id: str) -> Optional[List[Dict[str, Any]]]:
        """获取会话历史"""
        session = self._sessions.get(session_id)
        if not session:
            return None
        return session.turns

    def clear(self) -> None:
        with self._lock:
            self._sessions.clear()


_session_memory: Optional[SessionMemory] = None


def get_session_memory() -> SessionMemory:
    """获取全局会话记忆实例"""
    global _session_memory
    if _session_memory is None:
        _session_memory = SessionMemory()
    return _session_memory
