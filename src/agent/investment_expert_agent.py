#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
投资专家 Agent：基于工具结果与偏好输出建议
"""

import json
import logging
from typing import Any, Dict, List, Optional

from agent.decision_agent import _build_client, _get_env

logger = logging.getLogger(__name__)


class InvestmentExpertAgent:
    """投资专家 Agent"""

    def __init__(self, model: Optional[str] = None):
        self.client = _build_client()
        self.model = model or _get_env("OPENAI_MODEL") or _get_env("DEEPSEEK_MODEL") or "deepseek-chat"

    def summarize(
        self,
        user_query: str,
        tool_results: List[Dict[str, Any]],
        preferences: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        汇总工具结果并输出投资建议

        Args:
            user_query: 用户问题
            tool_results: 工具调用结果
            preferences: 投资偏好（可选）

        Returns:
            投资建议文本
        """
        pref_text = json.dumps(preferences or {}, ensure_ascii=False, default=str)
        tools_text = json.dumps(tool_results or [], ensure_ascii=False, default=str)

        system_prompt = (
            "你是资深投资专家，请结合工具结果与用户投资偏好，"
            "先说明数据覆盖情况，再给出摘要、数据要点、风险提示与操作建议。"
            "若数据缺失，明确说明原因，不要编造。"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query},
            {"role": "user", "content": f"投资偏好: {pref_text}"},
            {"role": "user", "content": f"工具结果: {tools_text}"},
        ]

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
        )
        return response.choices[0].message.content or ""