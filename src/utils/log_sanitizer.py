#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
日志脱敏工具
避免在日志中记录敏感信息
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, Optional


SENSITIVE_PATTERNS = [
    (r'(?:api[_-]?key|apikey)\s*[:=]\s*\S+', '[API_KEY_REDACTED]'),
    (r'(?:password|passwd|pwd)\s*[:=]\s*\S+', '[PASSWORD_REDACTED]'),
    (r'(?:secret|token)\s*[:=]\s*\S+', '[SECRET_REDACTED]'),
    (r'(?:jwt|bearer)\s+\S+', '[JWT_REDACTED]'),
    (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL_REDACTED]'),
    (r'\b1[3-9]\d{9}\b', '[PHONE_REDACTED]'),
]


def sanitize_log(message: str) -> str:
    """
    清洗日志消息
    
    移除敏感信息如 API key、密码、JWT 等
    """
    if not message:
        return message
    
    result = message
    for pattern, replacement in SENSITIVE_PATTERNS:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    
    return result


def hash_sensitive(value: str) -> str:
    """
    对敏感值进行哈希
    
    用于需要记录但不能明文的场景
    """
    if not value:
        return ""
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def mask_string(value: str, show_chars: int = 4) -> str:
    """
    掩码字符串
    
    保留前几位，其余用 * 替代
    """
    if not value:
        return ""
    if len(value) <= show_chars:
        return "*" * len(value)
    return value[:show_chars] + "*" * (len(value) - show_chars)


def sanitize_dict(data: Dict[str, Any], sensitive_keys: list = None) -> Dict[str, Any]:
    """
    清洗字典中的敏感字段
    """
    if sensitive_keys is None:
        sensitive_keys = [
            "api_key", "apikey", "password", "passwd", "pwd",
            "secret", "token", "jwt", "bearer", "authorization",
        ]
    
    result = {}
    for key, value in data.items():
        if any(s in key.lower() for s in sensitive_keys):
            if isinstance(value, str):
                result[key] = mask_string(value)
            else:
                result[key] = "[REDACTED]"
        elif isinstance(value, dict):
            result[key] = sanitize_dict(value, sensitive_keys)
        elif isinstance(value, list):
            result[key] = [
                sanitize_dict(item, sensitive_keys) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value
    
    return result


class SensitiveLogger:
    """敏感日志包装器"""

    def __init__(self, logger):
        self._logger = logger

    def _sanitize_args(self, args: tuple) -> tuple:
        """清洗参数"""
        return tuple(
            sanitize_log(str(arg)) if isinstance(arg, str) else arg
            for arg in args
        )

    def info(self, msg: str, *args, **kwargs):
        self._logger.info(sanitize_log(msg), *self._sanitize_args(args), **kwargs)

    def warning(self, msg: str, *args, **kwargs):
        self._logger.warning(sanitize_log(msg), *self._sanitize_args(args), **kwargs)

    def error(self, msg: str, *args, **kwargs):
        self._logger.error(sanitize_log(msg), *self._sanitize_args(args), **kwargs)

    def debug(self, msg: str, *args, **kwargs):
        self._logger.debug(sanitize_log(msg), *self._sanitize_args(args), **kwargs)
