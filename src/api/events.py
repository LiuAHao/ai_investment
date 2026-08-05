#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SSE 事件流 API
提供多 Agent 任务的实时事件推送（无 auth 版本）。
事件总线逻辑迁移至 services/event_bus.py，此处复用。
"""

from __future__ import annotations

import json
import logging
import queue
import time
from typing import Any, Dict, Generator, Optional

from flask import Blueprint, Response, jsonify

from services.event_bus import emit_event  # noqa: F401  (re-export)
from services.event_bus import event_bus

logger = logging.getLogger(__name__)

events_bp = Blueprint("events", __name__)

# 任务快照注册表（供 SSE 重连补发）
_task_snapshots: Dict[str, Dict[str, Any]] = {}


def save_task_snapshot(task_id: str, snapshot: Dict[str, Any]) -> None:
    """保存任务快照（供重连补发）"""
    _task_snapshots[task_id] = snapshot


def get_task_snapshot(task_id: str) -> Optional[Dict[str, Any]]:
    """获取任务快照"""
    return _task_snapshots.get(task_id)


def _sse(event_type: str, data: Dict[str, Any]) -> str:
    """格式化 SSE 数据帧（统一为 {type, data} 结构，与实时事件兼容）"""
    payload = json.dumps({
        "type": event_type,
        "data": data,
    }, ensure_ascii=False, default=str)
    return f"event: {event_type}\ndata: {payload}\n\n"


@events_bp.route("/events/<task_id>", methods=["GET"])
def stream_events(task_id: str):
    """
    SSE 事件流

    事件类型：
    - connected: 连接建立
    - task_started / task_completed / task_failed
    - orchestrator_thinking / orchestrator_decided
    - agent_started / agent_thinking / tool_* / agent_*
    - final_answer
    - heartbeat: 30s 心跳保活
    """
    snapshot = get_task_snapshot(task_id)

    def generate() -> Generator[str, None, None]:
        q = event_bus.subscribe(task_id)
        try:
            # 连接建立
            yield _sse("connected", {"task_id": task_id})

            # 任务已完成 → 补发快照
            if snapshot and snapshot.get("status") == "completed":
                yield _sse("task_completed", snapshot.get("result", {}))
                return
            if snapshot and snapshot.get("status") == "failed":
                yield _sse("task_failed", {"error": snapshot.get("error", "任务失败")})
                return

            # 实时事件
            while True:
                try:
                    event = q.get(timeout=30)
                    event_json = json.dumps(event, ensure_ascii=False, default=str)
                    yield f"event: {event['type']}\ndata: {event_json}\n\n"

                    if event["type"] in ("task_completed", "task_failed"):
                        break
                except queue.Empty:
                    yield _sse("heartbeat", {"timestamp": time.time()})
                except GeneratorExit:
                    break
        finally:
            event_bus.unsubscribe(task_id, q)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
