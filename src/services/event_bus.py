#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
通用事件总线
从旧 src/api/events.py 抽出，去除 auth 依赖，供 SSE 推送使用。
线程安全：使用锁保护订阅者集合。
"""

from __future__ import annotations

import queue
import threading
import time
from typing import Any, Dict, Optional


class EventBus:
    """通用事件总线

    维护 task_id -> [Queue] 的映射，多个订阅者可同时订阅同一任务事件。
    每个任务保留最近事件缓冲（供 SSE 连接建立较晚的订阅者补发）。
    """

    MAX_BUFFER = 200

    def __init__(self) -> None:
        self._subscribers: Dict[str, list] = {}
        self._buffers: Dict[str, list] = {}
        self._lock = threading.Lock()

    def subscribe(self, task_id: str) -> queue.Queue:
        """订阅任务事件，返回事件队列（含历史缓冲回放）"""
        q: queue.Queue = queue.Queue()
        with self._lock:
            # 回放历史缓冲（若有）
            for event in list(self._buffers.get(task_id, [])):
                try:
                    q.put_nowait(event)
                except queue.Full:
                    break
            self._subscribers.setdefault(task_id, []).append(q)
        return q

    def unsubscribe(self, task_id: str, q: queue.Queue) -> None:
        """取消订阅，队列为空时移除任务键"""
        with self._lock:
            subs = self._subscribers.get(task_id)
            if not subs:
                return
            try:
                subs.remove(q)
            except ValueError:
                pass
            if not subs:
                self._subscribers.pop(task_id, None)
                # 无订阅者时保留缓冲（供重连），仅清空队列对象
                self._buffers.setdefault(task_id, [])

    def publish(self, task_id: str, event: Dict[str, Any]) -> None:
        """向该任务所有订阅者发布事件，并写入历史缓冲"""
        with self._lock:
            # 写缓冲（保留最近 N 条）
            buffer = self._buffers.setdefault(task_id, [])
            buffer.append(event)
            if len(buffer) > self.MAX_BUFFER:
                del buffer[: len(buffer) - self.MAX_BUFFER]
            subscribers = list(self._subscribers.get(task_id, []))
        for q in subscribers:
            try:
                q.put_nowait(event)
            except queue.Full:
                pass


# 全局事件总线单例
event_bus = EventBus()


def emit_event(
    task_id: str, event_type: str, data: Optional[Dict[str, Any]] = None
) -> None:
    """发射事件（辅助函数）"""
    event = {
        "type": event_type,
        "task_id": task_id,
        "timestamp": time.time(),
        "data": data or {},
    }
    event_bus.publish(task_id, event)
