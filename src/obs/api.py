#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""可观测性诊断接口（只读）：任务、事件、统计、健康检查。"""

from __future__ import annotations

import os
from typing import Any, Dict

from flask import Blueprint, jsonify, request

from obs.store import get_store

ops_bp = Blueprint("ops", __name__, url_prefix="/api/ops")


def _authorized() -> bool:
    token = os.getenv("OPS_TOKEN", "")
    if not token:
        return True
    return request.headers.get("X-Ops-Token", "") == token


def _guard() -> Any:
    if not _authorized():
        return jsonify({"error": "unauthorized"}), 401
    return None


@ops_bp.get("/tasks")
def list_tasks():
    denied = _guard()
    if denied:
        return denied
    store = get_store()
    runs = store.list_runs(
        status=request.args.get("status"),
        limit=request.args.get("limit", 20),
        session_id=request.args.get("session_id"),
        since=request.args.get("since"),
    )
    return jsonify({"items": runs, "count": len(runs)})


@ops_bp.get("/tasks/<task_id>")
def task_detail(task_id: str):
    denied = _guard()
    if denied:
        return denied
    store = get_store()
    run = store.get_run(task_id)
    if not run:
        return jsonify({"error": "task not found", "task_id": task_id}), 404
    events = store.list_events(task_id, after_sequence=request.args.get("after", 0))
    detail: Dict[str, Any] = {
        "run": run,
        "events": events,
        "llm_calls": store.list_llm(task_id),
        "tool_calls": store.list_tools(task_id),
    }
    trace = run.get("trace_json")
    if trace:
        try:
            import json

            detail["trace"] = json.loads(trace)
        except Exception:
            detail["trace"] = None
    return jsonify(detail)


@ops_bp.get("/tasks/<task_id>/events")
def task_events(task_id: str):
    denied = _guard()
    if denied:
        return denied
    events = get_store().list_events(
        task_id,
        after_sequence=request.args.get("after", 0),
        limit=request.args.get("limit", 1000),
    )
    return jsonify({"items": events, "count": len(events)})


@ops_bp.get("/stats")
def stats():
    denied = _guard()
    if denied:
        return denied
    window = request.args.get("window", "24h")
    hours = 24
    try:
        text = str(window).strip().lower()
        if text.endswith("h"):
            hours = int(text[:-1])
        elif text.endswith("d"):
            hours = int(text[:-1]) * 24
        else:
            hours = int(text)
    except Exception:
        hours = 24
    return jsonify(get_store().stats(window_hours=hours))


@ops_bp.get("/health")
def health():
    denied = _guard()
    if denied:
        return denied
    health_info = get_store().health()
    healthy = bool(health_info.get("db_ok")) and (health_info.get("dropped") or 0) == 0
    health_info["status"] = "ok" if healthy else "degraded"
    return jsonify(health_info)
