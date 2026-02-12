#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Agent 协议定义（Phase 2）
统一各 Agent 的输入输出结构，便于替换与降级。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


TASK_PLAN_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "query": {"type": "string"},
        "symbol": {"type": ["string", "null"]},
        "tasks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "agent": {"type": "string"},
                    "task": {"type": "string"},
                    "params": {"type": "object"},
                },
                "required": ["agent", "task", "params"],
            },
        },
    },
    "required": ["query", "tasks"],
}


AGENT_RESULT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "agent": {"type": "string"},
        "status": {"type": "string", "enum": ["completed", "failed", "skipped"]},
        "data": {"type": "object"},
        "error": {"type": ["string", "null"]},
        "latency_ms": {"type": "integer"},
    },
    "required": ["agent", "status", "data", "error", "latency_ms"],
}


WORKFLOW_RESULT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "query": {"type": "string"},
        "symbol": {"type": ["string", "null"]},
        "degraded": {"type": "boolean"},
        "task_plan": {"type": "object"},
        "agent_results": {"type": "array", "items": AGENT_RESULT_SCHEMA},
        "recommendation": {"type": "string"},
        "created_at": {"type": "string"},
    },
    "required": [
        "query",
        "symbol",
        "degraded",
        "task_plan",
        "agent_results",
        "recommendation",
        "created_at",
    ],
}


@dataclass
class AgentResult:
    """统一 Agent 输出结构"""

    agent: str
    status: str
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    latency_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent": self.agent,
            "status": self.status,
            "data": self.data,
            "error": self.error,
            "latency_ms": self.latency_ms,
        }


@dataclass
class WorkflowResult:
    """统一工作流输出结构"""

    query: str
    symbol: Optional[str]
    degraded: bool
    task_plan: Dict[str, Any]
    agent_results: List[AgentResult]
    recommendation: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "symbol": self.symbol,
            "degraded": self.degraded,
            "task_plan": self.task_plan,
            "agent_results": [item.to_dict() for item in self.agent_results],
            "recommendation": self.recommendation,
            "created_at": self.created_at,
        }
