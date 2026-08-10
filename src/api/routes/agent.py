#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Agent 研究路由
提供多 Agent 研究的提交与 SSE 事件流接口。
"""

from __future__ import annotations

import concurrent.futures
import logging
import threading
import uuid
from typing import Any, Dict, Optional

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

agent_bp = Blueprint("agent_routes", __name__)

# 后台任务线程池
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

# 任务注册表（task_id -> {status, result, error}）
_tasks: Dict[str, Dict[str, Any]] = {}
_tasks_lock = threading.Lock()


def get_task(task_id: str) -> Optional[Dict[str, Any]]:
    """获取任务状态"""
    with _tasks_lock:
        return _tasks.get(task_id)


def _run_agent_task(task_id: str, session_id: str, query: str, risk_preference: str, context: str) -> None:
    """后台执行 Agent 研究"""
    from agents.orchestrator import OrchestratorAgent
    from api.events import save_task_snapshot, emit_event

    emit_event(task_id, "task_started", {"task_id": task_id, "session_id": session_id})
    try:
        orchestrator = OrchestratorAgent(task_id=task_id)
        result = orchestrator.run_query(
            session_id=session_id,
            query=query,
            risk_preference=risk_preference,
            context=context,
        )
        # 保存会话记忆
        _save_session_turn(session_id, query, result)
        # 任务完成
        emit_event(task_id, "task_completed", {"result": result})
        save_task_snapshot(task_id, {"status": "completed", "result": result})
        with _tasks_lock:
            if task_id in _tasks:
                _tasks[task_id]["status"] = "completed"
                _tasks[task_id]["result"] = result
    except Exception as e:
        logger.exception("Agent 研究任务失败: %s", e)
        emit_event(task_id, "task_failed", {"error": str(e)})
        save_task_snapshot(task_id, {"status": "failed", "error": str(e)})
        with _tasks_lock:
            if task_id in _tasks:
                _tasks[task_id]["status"] = "failed"
                _tasks[task_id]["error"] = str(e)


def _save_session_turn(session_id: str, query: str, result: Dict[str, Any]) -> None:
    """将研究结果写入会话（JSON 文件持久化）"""
    try:
        from agents.memory import get_session_memory
        from agents.state import InvestmentAnswer

        memory = get_session_memory()

        answer_data = result.get("answer", {})
        answer = InvestmentAnswer(**answer_data)

        agent_results = []
        for r in result.get("agent_results", []):
            # 工具调用信息：保留工具名/状态/耗时/结果摘要（data 可能很大，截断）
            tool_calls = []
            for tc in r.get("tool_calls", []):
                data = tc.get("data") or {}
                tool_calls.append({
                    "tool_name": tc.get("tool_name", ""),
                    "status": tc.get("status", "success"),
                    "latency_ms": tc.get("latency_ms", 0),
                    "error": tc.get("error"),
                    "summary": _tool_data_summary(data),
                })
            agent_results.append({
                "agent_name": r.get("agent_name", ""),
                "conclusion": r.get("conclusion", ""),
                "thinking_log": r.get("thinking_log", []),
                "evidence_refs": r.get("evidence_refs", []),
                "tool_calls": tool_calls,
                "error": r.get("error"),
                "degraded": r.get("degraded", False),
            })

        # 编排信息（供历史页还原主页展示：编排卡 + 按 plan 排工位）
        orch = result.get("orchestrator", {})
        orchestrator = {
            "thoughts": orch.get("thoughts", []),
            "plan": orch.get("plan", []),
            "reason": orch.get("reason", ""),
        }
        plan = result.get("plan", {}).get("agents", [])

        memory.add_turn(session_id, query, answer, agent_results, plan=plan, orchestrator=orchestrator)
    except Exception as e:
        logger.warning("保存会话记忆失败: %s", e)


def _tool_data_summary(data: Dict[str, Any]) -> str:
    """从工具返回数据中生成短摘要（避免把大数据存入会话记忆）"""
    if not data:
        return ""
    summary = data.get("summary") or data.get("conclusion") or data.get("answer")
    if summary:
        return str(summary)[:200]
    for key in ("items", "data", "results", "list", "rows"):
        value = data.get(key)
        if isinstance(value, list):
            return f"返回 {len(value)} 条数据"
    return str(data)[:120]


@agent_bp.route("/query", methods=["POST"])
def submit_query():
    """提交研究任务"""
    data = request.get_json(silent=True) or {}
    query = str(data.get("query", "")).strip()
    if not query:
        return jsonify({"error": "query 不能为空"}), 400

    session_id = str(data.get("session_id", "")).strip() or f"mem_{uuid.uuid4().hex[:12]}"
    risk_preference = str(data.get("risk_preference", "")).strip()
    context = str(data.get("context", "")).strip()

    task_id = f"task_{uuid.uuid4().hex[:12]}"
    with _tasks_lock:
        _tasks[task_id] = {"status": "processing"}

    _executor.submit(_run_agent_task, task_id, session_id, query, risk_preference, context)

    return jsonify({"task_id": task_id, "session_id": session_id}), 202


@agent_bp.route("/tasks/<task_id>", methods=["GET"])
def get_task_status(task_id: str):
    """查询任务状态"""
    task = get_task(task_id)
    if not task:
        return jsonify({"error": "任务不存在"}), 404
    return jsonify(task), 200
