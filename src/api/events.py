#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SSE 事件流 API
提供 V2 任务的实时事件推送
"""

from __future__ import annotations

import json
import logging
import queue
import threading
import time
from typing import Any, Dict, Generator, Optional

from flask import Blueprint, Response, jsonify, request

from api.auth import get_current_user
from models import get_db
from models.database import User
from services.task_service import TaskService
from utils.jwt_utils import decode_access_token

logger = logging.getLogger(__name__)

events_bp = Blueprint("events", __name__)


class EventBus:
    """事件总线"""

    def __init__(self):
        self._subscribers: Dict[str, list] = {}
        self._lock = threading.Lock()

    def subscribe(self, task_id: str) -> queue.Queue:
        """订阅任务事件"""
        q = queue.Queue()
        with self._lock:
            if task_id not in self._subscribers:
                self._subscribers[task_id] = []
            self._subscribers[task_id].append(q)
        return q

    def unsubscribe(self, task_id: str, q: queue.Queue) -> None:
        """取消订阅"""
        with self._lock:
            if task_id in self._subscribers:
                try:
                    self._subscribers[task_id].remove(q)
                except ValueError:
                    pass
                if not self._subscribers[task_id]:
                    del self._subscribers[task_id]

    def publish(self, task_id: str, event: Dict[str, Any]) -> None:
        """发布事件"""
        with self._lock:
            subscribers = self._subscribers.get(task_id, [])
            for q in subscribers:
                try:
                    q.put_nowait(event)
                except queue.Full:
                    pass


event_bus = EventBus()


def emit_event(task_id: str, event_type: str, data: Dict[str, Any] = None) -> None:
    """
    发射事件
    
    Args:
        task_id: 任务ID
        event_type: 事件类型
        data: 事件数据
    """
    event = {
        "type": event_type,
        "task_id": task_id,
        "timestamp": time.time(),
        "data": data or {},
    }
    event_bus.publish(task_id, event)


@events_bp.route("/events/<task_id>", methods=["GET"])
def stream_events(task_id: str):
    """
    SSE 事件流
    
    事件类型：
    - task_started: 任务开始
    - node_started: 节点开始
    - node_completed: 节点完成
    - tool_started: 工具开始
    - tool_completed: 工具完成
    - evidence_added: 证据添加
    - draft_created: 草稿创建
    - critic_completed: 评审完成
    - compliance_completed: 合规检查完成
    - task_completed: 任务完成
    - task_failed: 任务失败
    """
    user = get_current_user() or _get_user_from_query_token()
    if not user:
        return jsonify({"error": "未授权"}), 401

    task = TaskService.get_task(task_id)
    if not task:
        return jsonify({"error": "任务不存在"}), 404
    if task.user_id != user.id:
        return jsonify({"error": "无权访问该任务"}), 403

    def generate() -> Generator[str, None, None]:
        q = event_bus.subscribe(task_id)
        try:
            yield f"event: connected\ndata: {json.dumps({'task_id': task_id})}\n\n"
            
            while True:
                try:
                    event = q.get(timeout=30)
                    event_json = json.dumps(event, ensure_ascii=False)
                    yield f"event: {event['type']}\ndata: {event_json}\n\n"
                    
                    if event['type'] in ('task_completed', 'task_failed'):
                        break
                except queue.Empty:
                    yield f"event: heartbeat\ndata: {json.dumps({'timestamp': time.time()})}\n\n"
                except GeneratorExit:
                    break
        finally:
            event_bus.unsubscribe(task_id, q)

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        }
    )


def _get_user_from_query_token() -> Optional[User]:
    """EventSource 无法设置 Authorization header，允许通过 query token 鉴权"""
    token = request.args.get("token")
    if not token:
        return None

    payload = decode_access_token(token)
    if not payload:
        return None

    with get_db() as db:
        return db.query(User).filter_by(id=payload.get("user_id")).first()
