#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""可观测性入口：初始化存储、日志、诊断接口与 HTTP 访问日志。"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Optional

from obs.context import (
    bind,
    bind_context,
    current,
    current_task_id,
    set_agent,
    set_stage,
    unbind,
)
from obs.log_setup import init_logging
from obs.store import ObsStore, classify_error, get_store, now_iso, redact

_initialized = False
_init_lock = threading.Lock()

_access_logger = logging.getLogger("obs.access")


def enabled() -> bool:
    return os.getenv("OBS_ENABLED", "1") not in ("0", "false", "no", "off")


def init_observability(app=None) -> ObsStore:
    """初始化观测库 + JSONL 日志 + 诊断蓝图 + 访问日志。幂等。"""
    global _initialized
    store = get_store()
    if not enabled():
        return store
    with _init_lock:
        if not _initialized:
            store.start()
            init_logging()
            store.cleanup(
                run_days=int(os.getenv("OBS_RUN_RETENTION_DAYS", "90")),
                event_days=int(os.getenv("OBS_EVENT_RETENTION_DAYS", "30")),
            )
            _initialized = True
    if app is not None:
        try:
            from obs.api import ops_bp

            if "ops.list_tasks" not in app.view_functions:
                app.register_blueprint(ops_bp)
                _install_access_log(app)
        except Exception:
            pass
    return store


def shutdown_observability() -> None:
    get_store().stop()


def _install_access_log(app) -> None:
    @app.before_request
    def _obs_before():
        from flask import g

        g._obs_started = time.time()

    @app.after_request
    def _obs_after(response):
        try:
            from flask import g, request

            if request.path.startswith("/api/") and not request.path.startswith("/api/ops"):
                duration = int((time.time() - getattr(g, "_obs_started", time.time())) * 1000)
                _access_logger.info(
                    "http_access",
                    extra={
                        "event": "http_access",
                        "method": request.method,
                        "path": request.path,
                        "http_status": response.status_code,
                        "duration_ms": duration,
                        "task_id": current_task_id(),
                    },
                )
        except Exception:
            pass
        return response


def record_run_start(
    task_id: str,
    session_id: str = "",
    query: str = "",
    source: str = "agent",
    model: str = "",
) -> None:
    if not enabled():
        return
    try:
        get_store().run_start(task_id, session_id, query, source=source, model=model)
    except Exception:
        pass


def update_run(task_id: str, **fields: Any) -> None:
    if not enabled():
        return
    try:
        get_store().run_update(task_id, **fields)
    except Exception:
        pass


def finish_run(task_id: str, status: str, error: Any = "", **fields: Any) -> None:
    if not enabled():
        return
    try:
        get_store().run_finish(
            task_id,
            status,
            error_type=classify_error(error) if error else "",
            error=str(error or ""),
            **fields,
        )
    except Exception:
        pass


__all__ = [
    "ObsStore",
    "bind",
    "bind_context",
    "classify_error",
    "current",
    "current_task_id",
    "enabled",
    "finish_run",
    "get_store",
    "init_observability",
    "now_iso",
    "record_run_start",
    "redact",
    "set_agent",
    "set_stage",
    "shutdown_observability",
    "unbind",
    "update_run",
]
