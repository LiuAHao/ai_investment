#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
任务服务
管理 V2 异步任务
"""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class TaskInfo:
    """任务信息"""

    def __init__(self, task_id: str, session_id: str, user_id: int):
        self.task_id = task_id
        self.session_id = session_id
        self.user_id = user_id
        self.status = "pending"
        self.progress = 0
        self.current_node: Optional[str] = None
        self.result: Optional[Dict[str, Any]] = None
        self.error: Optional[str] = None
        self.trace: list = []
        self.created_at = time.time()
        self.completed_at: Optional[float] = None
        self.timeout_seconds: Optional[int] = None


class TaskService:
    """任务服务"""

    _tasks: Dict[str, TaskInfo] = {}
    _lock = threading.Lock()
    _executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="v2_task")

    @classmethod
    def create_task(cls, session_id: str, user_id: int) -> str:
        """创建任务"""
        import uuid
        task_id = str(uuid.uuid4())
        with cls._lock:
            cls._tasks[task_id] = TaskInfo(task_id, session_id, user_id)
        return task_id

    @classmethod
    def get_task(cls, task_id: str) -> Optional[TaskInfo]:
        """获取任务"""
        return cls._tasks.get(task_id)

    @classmethod
    def submit_task(
        cls,
        task_id: str,
        func: Callable,
        *args,
        timeout_seconds: Optional[int] = None,
        **kwargs,
    ) -> None:
        """提交任务执行"""
        def wrapper():
            task = cls.get_task(task_id)
            if task:
                task.status = "processing"
                task.timeout_seconds = timeout_seconds
                started_at = time.time()
                try:
                    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="v2_task_inner")
                    future = pool.submit(func, *args, **kwargs)
                    try:
                        result = future.result(timeout=timeout_seconds)
                    finally:
                        pool.shutdown(wait=False, cancel_futures=True)
                    elapsed = time.time() - started_at
                    if timeout_seconds and elapsed > timeout_seconds:
                        task.status = "timeout"
                        task.error = f"任务执行超时: {timeout_seconds}s"
                        task.completed_at = time.time()
                        return
                    task.status = "completed"
                    task.result = result
                    task.progress = 100
                    task.completed_at = time.time()
                except TimeoutError:
                    task.status = "timeout"
                    task.error = f"任务执行超时: {timeout_seconds}s"
                    task.completed_at = time.time()
                except Exception as e:
                    task.status = "failed"
                    task.error = str(e)
                    task.completed_at = time.time()

        cls._executor.submit(wrapper)

    @classmethod
    def update_task_progress(cls, task_id: str, progress: int, node: str = None) -> None:
        """更新任务进度"""
        task = cls.get_task(task_id)
        if task:
            task.progress = progress
            if node:
                task.current_node = node

    @classmethod
    def cleanup_expired(cls, max_age: int = 3600) -> None:
        """清理过期任务"""
        now = time.time()
        with cls._lock:
            expired = [
                tid for tid, task in cls._tasks.items()
                if task.completed_at and now - task.completed_at > max_age
            ]
            for tid in expired:
                del cls._tasks[tid]
