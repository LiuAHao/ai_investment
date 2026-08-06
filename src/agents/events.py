#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Agent 事件发射
统一封装面向 SSE 推送的 Agent 级事件，所有 Agent 通过此模块发射进度事件。

事件协议：
- orchestrator_thinking / orchestrator_decided
- agent_started / agent_thinking / tool_started / tool_completed / tool_failed
- agent_failed / agent_completed
- final_answer
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional


def _emit(task_id: str, event_type: str, data: Dict[str, Any]) -> None:
    """发射事件（异步安全，线程池中调用）"""
    try:
        from api.events import emit_event
        emit_event(task_id, event_type, data)
    except Exception:
        # 事件发射失败不影响 Agent 主流程
        pass


def orchestrator_thinking(task_id: str, thought: str) -> None:
    _emit(task_id, "orchestrator_thinking", {"thought": thought})


def orchestrator_decided(task_id: str, plan: list, reason: str) -> None:
    _emit(task_id, "orchestrator_decided", {"plan": plan, "reason": reason})


def agent_started(task_id: str, agent: str, task: str, goal: str, round: int = 1) -> None:
    _emit(task_id, "agent_started", {"agent": agent, "task": task, "goal": goal, "round": round})


def agent_thinking(task_id: str, agent: str, thought: str) -> None:
    _emit(task_id, "agent_thinking", {"agent": agent, "thought": thought})


def tool_started(task_id: str, agent: str, tool: str, params: Dict[str, Any]) -> None:
    _emit(task_id, "tool_started", {"agent": agent, "tool": tool, "params": params})


def tool_completed(
    task_id: str,
    agent: str,
    tool: str,
    status: str,
    latency: int,
    summary: Optional[str] = None,
) -> None:
    _emit(task_id, "tool_completed", {
        "agent": agent,
        "tool": tool,
        "status": status,
        "latency": latency,
        "summary": summary or "",
    })


def tool_failed(task_id: str, agent: str, tool: str, error: str) -> None:
    _emit(task_id, "tool_failed", {"agent": agent, "tool": tool, "error": error})


def agent_failed(task_id: str, agent: str, error: str) -> None:
    _emit(task_id, "agent_failed", {"agent": agent, "error": error})


def agent_completed(task_id: str, agent: str, result_summary: str, evidence_refs: list, round: int = 1) -> None:
    _emit(task_id, "agent_completed", {
        "agent": agent,
        "result_summary": result_summary,
        "evidence_refs": evidence_refs,
        "round": round,
    })


def final_answer(task_id: str, answer: Dict[str, Any]) -> None:
    _emit(task_id, "final_answer", {"answer": answer})


def task_time_marker(task_id: str, label: str) -> None:
    _emit(task_id, "task_marker", {"label": label, "ts": time.time()})
