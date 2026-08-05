#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
BaseReActAgent 抽象基类
所有调研 Agent 与总结 Agent 的公共基类。

职责：
1. 加载上下文（会话/追问历史）
2. 执行 ReAct 循环（loop.py）
3. 产出 AgentResult（结论 + 证据 + 工具记录 + 思考轨迹）
4. 全程发射 agent_* / tool_* 事件
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from openai import OpenAI

from utils.llm_common import build_client
from agents import events
from agents.loop import ReActLoop
from agents.state import AgentResult, AgentTask, ToolResult

logger = logging.getLogger(__name__)


class BaseReActAgent:
    """
    ReAct Agent 基类

    Attributes:
        name: Agent 名称（如 "MarketAgent"）
        description: 职责描述（给编排 Agent 看）
        tool_names: 本 Agent 可用的工具白名单
        system_prompt: 角色与目标
        max_iterations: ReAct 循环安全上限
        model: LLM 模型名（默认读环境变量）
    """

    name: str = ""
    description: str = ""
    tool_names: List[str] = []
    system_prompt: str = ""
    max_iterations: int = 8

    def __init__(self, task_id: str = "", model: Optional[str] = None):
        self.task_id = task_id
        self._client: Optional[OpenAI] = None
        self._model = model
        self._tool_schemas_cache: Optional[List[Dict[str, Any]]] = None
        self.max_iterations = self._resolve_max_iterations()

    def _resolve_max_iterations(self) -> int:
        """
        迭代上限取值：环境变量 AGENT_MAX_ITERATIONS 优先（全局统一覆盖），
        否则使用类属性（MarketAgent=8 / NewsAgent=6 / KnowledgeAgent=6 / SummaryAgent=8）。
        """
        raw = os.getenv("AGENT_MAX_ITERATIONS", "").strip()
        if raw.isdigit() and int(raw) > 0:
            return int(raw)
        return self.__class__.max_iterations

    # ---------- 公共入口 ----------

    def run(self, task: AgentTask) -> AgentResult:
        """执行 Agent 任务"""
        events.agent_started(self.task_id, self.name, task.goal, task.goal)

        loop = ReActLoop(
            client=self._get_client(),
            model=self._get_model(),
            system_prompt=self._build_prompt(task),
            tool_schemas=self._get_tool_schemas(),
            execute_tool=self._execute_tool,
            task_id=self.task_id,
            agent_name=self.name,
            max_iterations=self.max_iterations,
        )

        try:
            result = loop.run(self._build_user_message(task))
            events.agent_completed(
                self.task_id, self.name,
                result_summary=result.conclusion,
                evidence_refs=result.evidence_refs,
            )
            return result
        except Exception as e:
            logger.exception("[%s] Agent 执行失败: %s", self.name, e)
            events.agent_failed(self.task_id, self.name, str(e))
            return AgentResult(
                agent_name=self.name,
                conclusion=f"研究过程中发生错误: {e}",
                error=str(e),
                thinking_log=[],
                degraded=True,
            )

    # ---------- 子类可覆盖 ----------

    def _build_prompt(self, task: AgentTask) -> str:
        """构建 system prompt（子类可扩展）"""
        return self.system_prompt

    def _build_user_message(self, task: AgentTask) -> str:
        """构建用户消息（子类可扩展）"""
        parts = [f"研究目标：{task.goal}"]
        if task.assets:
            asset_names = ", ".join(a.name or a.symbol or "" for a in task.assets)
            parts.append(f"涉及资产：{asset_names}")
        if task.context:
            parts.append(f"上下文：\n{task.context}")
        return "\n".join(parts)

    # ---------- 工具 ----------

    def _get_tool_schemas(self) -> List[Dict[str, Any]]:
        """获取本 Agent 可见工具 schema（按白名单过滤）"""
        if self._tool_schemas_cache is not None:
            return self._tool_schemas_cache
        from tools.registry import get_tool_registry
        registry = get_tool_registry()
        schemas = []
        for spec in registry.get_all_specs():
            if self.tool_names and spec.name not in self.tool_names:
                continue
            schema = spec.model_dump()
            schemas.append(schema)
        self._tool_schemas_cache = schemas
        return schemas

    def _execute_tool(self, tool_name: str, params: Dict[str, Any]) -> ToolResult:
        """执行工具（带白名单校验）"""
        if self.tool_names and tool_name not in self.tool_names:
            return ToolResult(
                tool_name=tool_name,
                status="failed",
                error=f"工具 {tool_name} 不在本 Agent 白名单中",
                confidence=0.0,
            )
        from tools.registry import get_tool_registry
        registry = get_tool_registry()
        return registry.execute(tool_name, params)

    # ---------- 基础设施 ----------

    def _get_client(self) -> OpenAI:
        if self._client is None:
            self._client = build_client()
        return self._client

    def _get_model(self) -> str:
        if self._model:
            return self._model
        import os
        from utils.llm_common import get_env
        return get_env("AGENT_LLM_MODEL", "deepseek-chat")
