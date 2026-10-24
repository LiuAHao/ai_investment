#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
会话记忆
进程内内存态会话管理 + JSON 文件持久化（重启不丢失）。

持久化说明：
- 会话列表与 turns 在每次变更后落盘到 SESSIONS_FILE（JSON）
- context / last_answer 属运行期追问上下文，不持久化
- 文件损坏/不可写时自动降级为纯内存态，不影响主流程
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from agents.state import Asset, InvestmentAnswer, ResearchContext

logger = logging.getLogger(__name__)

# 会话持久化文件（相对本模块：src/data/sessions.json）
SESSIONS_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "sessions.json")
)

# 保留上限：单会话回合数 / 会话数 / 落盘文件大小
MAX_TURNS_PER_SESSION = 200
MAX_SESSIONS = 200
MAX_FILE_BYTES = 20 * 1024 * 1024
SAVE_ERROR_LOG_INTERVAL = 60  # 秒，同类落盘错误的最小日志间隔


class MemorySession:
    """单个会话（内存对象 + 可序列化）"""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.turns: List[Dict[str, Any]] = []
        self.context: Optional[ResearchContext] = None
        self.last_answer: Optional[InvestmentAnswer] = None

    def add_turn(
        self,
        query: str,
        answer: InvestmentAnswer,
        agent_results: List[Dict[str, Any]],
        plan: Optional[List[str]] = None,
        orchestrator: Optional[Dict[str, Any]] = None,
        extras: Optional[Dict[str, Any]] = None,
    ) -> None:
        turn: Dict[str, Any] = {
            "query": query,
            # mode="json"：datetime 等字段转 ISO 字符串，保证 JSON 可序列化
            "answer": answer.model_dump(mode="json"),
            "agent_results": agent_results,
            "timestamp": datetime.now().isoformat(),
        }
        if plan is not None:
            turn["plan"] = plan
        if orchestrator is not None:
            turn["orchestrator"] = orchestrator
        if extras:
            turn.update(extras)
        self.turns.append(turn)
        self.last_answer = answer
        self.updated_at = datetime.now()

    # ---------- 序列化 ----------

    def to_dict(self) -> Dict[str, Any]:
        """持久化用：只保存 turns 与时间（context/last_answer 为运行期数据）"""
        return {
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "turns": self.turns,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemorySession":
        """从持久化数据恢复会话（容错：字段缺失时使用默认值）"""
        session = cls(str(data.get("session_id", "")))
        try:
            session.created_at = datetime.fromisoformat(str(data.get("created_at", "")))
        except ValueError:
            pass
        try:
            session.updated_at = datetime.fromisoformat(str(data.get("updated_at", "")))
        except ValueError:
            pass
        turns = data.get("turns") or []
        if isinstance(turns, list):
            session.turns = [t for t in turns if isinstance(t, dict)]
        return session


class SessionMemory:
    """会话记忆管理器（进程内单例 + JSON 文件持久化）"""

    def __init__(self, file_path: Optional[str] = None):
        self._file = file_path or SESSIONS_FILE
        self._sessions: Dict[str, MemorySession] = {}
        self._lock = threading.Lock()
        self._save_lock = threading.Lock()
        self._last_save_error_ts = 0.0
        self._load()

    # ---------- 持久化 ----------

    def _load(self) -> None:
        """启动时从文件加载会话（容错：文件不存在/损坏时保持空）"""
        try:
            if not os.path.exists(self._file):
                return
            with open(self._file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                logger.warning("会话持久化文件格式异常，忽略: %s", self._file)
                return
            for sid, raw in data.items():
                if not isinstance(raw, dict):
                    continue
                try:
                    session = MemorySession.from_dict(raw)
                    if session.session_id:
                        self._sessions[session.session_id] = session
                except Exception as exc:
                    logger.warning("恢复会话 %s 失败: %s", sid, exc)
            if self._sessions:
                logger.info("已从 %s 恢复 %d 个会话", self._file, len(self._sessions))
        except Exception as exc:
            logger.warning("加载会话持久化文件失败（降级为内存态）: %s", exc)

    def _save(self) -> None:
        """
        全量落盘（会话量小，全量写入简单可靠；失败不影响主流程）。
        并发安全：独立写锁串行化写入，临时文件名含进程/线程标识，避免互相覆盖。
        """
        with self._save_lock:
            try:
                text = self._serialize_bounded()
                tmp = f"{self._file}.{os.getpid()}.{threading.get_ident()}.tmp"
                os.makedirs(os.path.dirname(self._file), exist_ok=True)
                with open(tmp, "w", encoding="utf-8") as f:
                    f.write(text)
                os.replace(tmp, self._file)  # 原子替换，避免写一半损坏
            except Exception as exc:
                now = time.time()
                if now - self._last_save_error_ts >= SAVE_ERROR_LOG_INTERVAL:
                    self._last_save_error_ts = now
                    logger.warning("会话持久化写入失败（同类错误 %ss 内只记录一次）: %s", SAVE_ERROR_LOG_INTERVAL, exc)

    def _serialize_bounded(self) -> str:
        """序列化并执行保留策略：先淘汰最旧会话，再按文件大小逐步收紧"""
        with self._lock:
            if len(self._sessions) > MAX_SESSIONS:
                self._trim_oldest_sessions(len(self._sessions) - MAX_SESSIONS)
            text = json.dumps(
                {sid: s.to_dict() for sid, s in self._sessions.items()},
                ensure_ascii=False,
                indent=2,
            )
            # 超出大小上限：淘汰最旧会话后重新序列化，直到满足或只剩一个会话
            while len(text.encode("utf-8")) > MAX_FILE_BYTES and len(self._sessions) > 1:
                self._trim_oldest_sessions(1)
                text = json.dumps(
                    {sid: s.to_dict() for sid, s in self._sessions.items()},
                    ensure_ascii=False,
                    indent=2,
                )
            return text

    def _trim_oldest_sessions(self, count: int) -> None:
        """淘汰最旧的 count 个会话（调用方需持有 self._lock）"""
        if count <= 0:
            return
        ordered = sorted(self._sessions.values(), key=lambda s: s.updated_at)
        for session in ordered[:count]:
            self._sessions.pop(session.session_id, None)

    # ---------- 会话操作 ----------

    def create_session(self) -> MemorySession:
        session_id = f"mem_{uuid.uuid4().hex[:12]}"
        with self._lock:
            session = MemorySession(session_id)
            self._sessions[session_id] = session
        self._save()
        logger.info("创建会话: %s", session_id)
        return session

    def get_session(self, session_id: str) -> Optional[MemorySession]:
        return self._sessions.get(session_id)

    def get_or_create(self, session_id: str) -> MemorySession:
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = MemorySession(session_id)
        return self._sessions[session_id]

    def add_turn(
        self,
        session_id: str,
        query: str,
        answer: InvestmentAnswer,
        agent_results: List[Dict[str, Any]],
        plan: Optional[List[str]] = None,
        orchestrator: Optional[Dict[str, Any]] = None,
        extras: Optional[Dict[str, Any]] = None,
    ) -> None:
        """追加一轮并落盘"""
        session = self.get_or_create(session_id)
        with self._lock:
            session.add_turn(
                query, answer, agent_results,
                plan=plan, orchestrator=orchestrator, extras=extras,
            )
            if len(session.turns) > MAX_TURNS_PER_SESSION:
                del session.turns[: len(session.turns) - MAX_TURNS_PER_SESSION]
        self._save()

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
        """清空会话并落盘"""
        with self._lock:
            self._sessions.clear()
        self._save()


_session_memory: Optional[SessionMemory] = None


def get_session_memory() -> SessionMemory:
    """获取全局会话记忆实例"""
    global _session_memory
    if _session_memory is None:
        _session_memory = SessionMemory()
    return _session_memory
