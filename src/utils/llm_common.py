#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LLM 公共工具
提供环境变量读取与 OpenAI 客户端构建能力。
"""

import os

from openai import OpenAI


def get_env(name: str, default: str = "") -> str:
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


def build_client() -> OpenAI:
    load_env_file()
    api_key = get_env("DEEPSEEK_API_KEY") or get_env("OPENAI_API_KEY")
    base_url = get_env("DEEPSEEK_BASE_URL") or get_env("OPENAI_BASE_URL")
    if base_url:
        return OpenAI(api_key=api_key, base_url=base_url)
    return OpenAI(api_key=api_key)


class AgentConfig:
    """Agent 编排配置管理器（单例）"""

    _instance = None

    def __new__(cls) -> "AgentConfig":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    def __init__(self) -> None:
        if self._loaded:
            return
        load_env_file()

        # 编排器模式: auto | langchain | custom
        self.orchestrator_mode: str = get_env("AGENT_ORCHESTRATOR", "auto").strip().lower()

        # 数据收集 Agent 是否并行执行
        self.parallel_enabled: bool = get_env("AGENT_PARALLEL", "true").strip().lower() in ("true", "1", "yes")

        # 并行执行超时（秒）
        self.parallel_timeout: int = int(get_env("AGENT_PARALLEL_TIMEOUT", "30"))

        self._loaded = True

    def reload(self) -> None:
        """重新从环境变量加载配置"""
        self._loaded = False
        self.__init__()
