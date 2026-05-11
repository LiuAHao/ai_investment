#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
V2 API 基础 Schema 与任务服务测试
"""

import os
import sys

CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_SRC = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
if PROJECT_SRC not in sys.path:
    sys.path.insert(0, PROJECT_SRC)

from agent.v2.schemas import QueryRequest
from services.task_service import TaskService


def test_query_request_validates_query_length():
    """V2 查询请求应校验 query 长度"""
    payload = QueryRequest.model_validate({"query": "分析宁德时代", "preferences": {"risk": "稳健"}})

    assert payload.query == "分析宁德时代"
    assert payload.preferences["risk"] == "稳健"


def test_task_service_records_user_id_for_authorization():
    """任务服务应记录 user_id，供状态查询做越权校验"""
    task_id = TaskService.create_task(session_id="session-test", user_id=123)
    task = TaskService.get_task(task_id)

    assert task is not None
    assert task.task_id == task_id
    assert task.session_id == "session-test"
    assert task.user_id == 123


def test_task_service_emits_completion_event(monkeypatch):
    """任务完成时应向 SSE 总线发送完成事件"""
    emitted = []

    def fake_emit_event(task_id, event_type, data=None):
        emitted.append((task_id, event_type, data or {}))

    import api.events

    monkeypatch.setattr(api.events, "emit_event", fake_emit_event)

    task_id = TaskService.create_task(session_id="session-event", user_id=123)
    TaskService.submit_task(task_id, lambda: {"trace": [], "final_answer": "ok"})

    import time
    deadline = time.time() + 2
    while time.time() < deadline:
        task = TaskService.get_task(task_id)
        if task and task.status == "completed":
            break
        time.sleep(0.01)

    event_types = [event_type for _, event_type, _ in emitted]
    assert "task_started" in event_types
    assert "task_completed" in event_types


def test_event_bus_publish_subscribe_roundtrip():
    """事件总线应能按 task_id 发布和订阅消息"""
    from api.events import EventBus

    bus = EventBus()
    queue = bus.subscribe("task-1")
    bus.publish("task-1", {"type": "task_completed", "data": {"ok": True}})

    event = queue.get(timeout=1)

    assert event["type"] == "task_completed"
    assert event["data"]["ok"] is True
