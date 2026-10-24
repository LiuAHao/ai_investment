#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LLM 公共工具
提供环境变量读取与 OpenAI 客户端构建能力。
"""

import os

from openai import OpenAI


_ENV_LOADED = False


def get_env(name: str, default: str = "") -> str:
    """读取环境变量（首次调用自动加载项目 .env）"""
    global _ENV_LOADED
    if not _ENV_LOADED:
        load_env_file()
        _ENV_LOADED = True
    value = os.getenv(name)
    return value if value is not None else default


def load_env_file() -> None:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    env_path = os.path.join(project_root, ".env")
    if not os.path.isfile(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception:
        pass


def build_client(timeout: float = 120.0, max_retries: int = 0) -> OpenAI:
    """
    构建 OpenAI 兼容客户端。

    Args:
        timeout: 单次请求读超时（秒），默认 120（原 SDK 默认 600s 过长）
        max_retries: SDK 层重试次数，默认 0（由调用方显式控制，避免叠加放大）
    """
    load_env_file()
    api_key = get_env("DEEPSEEK_API_KEY") or get_env("OPENAI_API_KEY")
    base_url = get_env("DEEPSEEK_BASE_URL") or get_env("OPENAI_BASE_URL")
    kwargs = {"api_key": api_key, "timeout": timeout, "max_retries": max_retries}
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)
