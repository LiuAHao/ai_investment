#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
总编排入口（Supervisor）

v4 起编排逻辑移到 agents/pipeline.py，本类只保留对外接口，
避免 api 层与测试代码大范围改动。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from agents.pipeline import Pipeline


class OrchestratorAgent:
    """投研编排器（Pipeline 的薄封装）"""

    name = "OrchestratorAgent"

    def __init__(self, task_id: str = "", model: Optional[str] = None):
        self.task_id = task_id
        self.model = model
        self.pipeline = Pipeline(task_id=task_id, model=model)

    def run_query(
        self,
        session_id: str,
        query: str,
        risk_preference: str = "",
        context: str = "",
        as_of: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self.pipeline.run(
            session_id=session_id,
            query=query,
            risk_preference=risk_preference,
            context=context,
            as_of=as_of,
        )
