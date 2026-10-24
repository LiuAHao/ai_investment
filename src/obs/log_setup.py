#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""结构化 JSON 日志：自动注入 task_id / stage / agent，并对敏感字段脱敏。"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Any, Dict

from obs.context import current
from obs.store import redact

_EXTRA_FIELDS = (
    "event", "task_id", "session_id", "stage", "agent", "duration_ms",
    "status", "error_type", "method", "path", "http_status", "model",
    "tool", "source",
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        payload.update({key: value for key, value in current().items() if value})
        for field in _EXTRA_FIELDS:
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(redact(payload), ensure_ascii=False, default=str)


def init_logging(log_dir: str | None = None) -> None:
    """给 root logger 挂一个 JSONL 文件 handler（幂等）。控制台日志保留原样。"""
    root = logging.getLogger()
    for handler in root.handlers:
        if getattr(handler, "_obs_json_handler", False):
            return
    directory = log_dir or os.getenv("OBS_LOG_DIR") or os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs"
    )
    try:
        os.makedirs(directory, exist_ok=True)
        handler = RotatingFileHandler(
            os.path.join(directory, "app.jsonl"),
            maxBytes=50 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        handler.setFormatter(JsonFormatter())
        handler._obs_json_handler = True  # type: ignore[attr-defined]
        root.addHandler(handler)
        if root.level > logging.INFO:
            root.setLevel(logging.INFO)
    except Exception:
        pass
