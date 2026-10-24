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


def plan_ready(task_id: str, plan: Dict[str, Any]) -> None:
    """研究计划（v4 语义，前端可逐步切换）"""
    _emit(task_id, "plan_ready", {"plan": plan})


def phase_started(task_id: str, phase: str, label: str = "", agents: Optional[list] = None) -> None:
    _emit(task_id, "phase_started", {
        "phase": phase,
        "label": label or phase,
        "agents": agents or [],
    })


def phase_completed(
    task_id: str,
    phase: str,
    duration_ms: int,
    degraded: bool = False,
    detail: Optional[Dict[str, Any]] = None,
) -> None:
    _emit(task_id, "phase_completed", {
        "phase": phase,
        "duration_ms": int(duration_ms),
        "degraded": bool(degraded),
        "detail": detail or {},
    })


def evidence_added(task_id: str, evidence: Dict[str, Any], total: int) -> None:
    _emit(task_id, "evidence_added", {
        "evidence_id": evidence.get("evidence_id", ""),
        "agent": evidence.get("_agent", ""),
        "category": evidence.get("category", ""),
        "statement": evidence.get("statement", ""),
        "value": evidence.get("value"),
        "unit": evidence.get("unit", ""),
        "caliber": evidence.get("caliber", ""),
        "source_time": evidence.get("source_time", ""),
        "conflict": bool(evidence.get("conflict")),
        "total": total,
    })


def thesis_started(task_id: str, side: str) -> None:
    _emit(task_id, "thesis_started", {"side": side, "status": "running"})


def thesis_submitted(
    task_id: str,
    side: str,
    claim_count: int,
    confidence: float,
    core_claim: str,
    claims: Optional[List[Dict[str, Any]]] = None,
) -> None:
    _emit(task_id, "thesis_submitted", {
        "side": side,
        "claim_count": int(claim_count),
        "confidence": float(confidence),
        "core_claim": core_claim,
        "claims": claims or [],
        "status": "done",
    })


def debate_turn(task_id: str, turn: Dict[str, Any]) -> None:
    _emit(task_id, "debate_turn", turn)


def verdict_ready(task_id: str, verdict: Dict[str, Any]) -> None:
    _emit(task_id, "verdict_ready", verdict)


def verification_failed(task_id: str, issues: list, retry_target: str = "") -> None:
    _emit(task_id, "verification_failed", {"issues": issues, "retry_target": retry_target})


def decision_recorded(task_id: str, decision_id: str, as_of: str, horizon: str) -> None:
    _emit(task_id, "decision_recorded", {
        "decision_id": decision_id,
        "as_of": as_of,
        "horizon": horizon,
    })


def agent_started(task_id: str, agent: str, task: str, goal: str, round: int = 1, stage: str = "") -> None:
    _emit(task_id, "agent_started", {
        "agent": agent, "task": task, "goal": goal, "round": round, "stage": stage,
    })


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


def agent_degraded(task_id: str, agent: str, reason: str, permanent: bool = False) -> None:
    """Agent 降级（原生 function calling 不可用，改为文本工具协议）"""
    _emit(task_id, "agent_degraded", {
        "agent": agent,
        "reason": reason,
        "permanent": permanent,
    })


def agent_completed(
    task_id: str,
    agent: str,
    result_summary: str,
    evidence_refs: list,
    round: int = 1,
    stage: str = "",
) -> None:
    _emit(task_id, "agent_completed", {
        "agent": agent,
        "result_summary": result_summary,
        "evidence_refs": evidence_refs,
        "round": round,
        "stage": stage,
    })


def final_answer(task_id: str, answer: Dict[str, Any]) -> None:
    _emit(task_id, "final_answer", {"answer": answer})


def task_time_marker(task_id: str, label: str) -> None:
    _emit(task_id, "task_marker", {"label": label, "ts": time.time()})
