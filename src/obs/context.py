#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""可观测性上下文：task_id / session_id / stage / agent 的线程与协程安全传递。"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Dict, Iterator, Optional

_task_id: ContextVar[str] = ContextVar("obs_task_id", default="")
_session_id: ContextVar[str] = ContextVar("obs_session_id", default="")
_stage: ContextVar[str] = ContextVar("obs_stage", default="")
_agent: ContextVar[str] = ContextVar("obs_agent", default="")


def bind(
    task_id: Optional[str] = None,
    session_id: Optional[str] = None,
    stage: Optional[str] = None,
    agent: Optional[str] = None,
) -> Dict[str, Token]:
    """绑定上下文，返回 token 供 unbind 使用。"""
    tokens: Dict[str, Token] = {}
    if task_id is not None:
        tokens["task_id"] = _task_id.set(task_id)
    if session_id is not None:
        tokens["session_id"] = _session_id.set(session_id)
    if stage is not None:
        tokens["stage"] = _stage.set(stage)
    if agent is not None:
        tokens["agent"] = _agent.set(agent)
    return tokens


def unbind(tokens: Dict[str, Token]) -> None:
    for key, token in (tokens or {}).items():
        try:
            {"task_id": _task_id, "session_id": _session_id, "stage": _stage, "agent": _agent}[key].reset(token)
        except Exception:
            pass


@contextmanager
def bind_context(**kwargs) -> Iterator[None]:
    tokens = bind(**kwargs)
    try:
        yield
    finally:
        unbind(tokens)


def set_stage(stage: str) -> None:
    _stage.set(stage or "")


def set_agent(agent: str) -> None:
    _agent.set(agent or "")


def current() -> Dict[str, str]:
    return {
        "task_id": _task_id.get(),
        "session_id": _session_id.get(),
        "stage": _stage.get(),
        "agent": _agent.get(),
    }


def current_task_id() -> str:
    return _task_id.get()
