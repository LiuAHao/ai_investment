#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
分析 Agent（Phase 2）
负责整合多 Agent 输出并生成最终建议。
"""

import json
from typing import Any, Dict, Optional

from agent.llm_common import build_client, get_env


class AnalysisAgent:
    """分析决策 Agent"""

    def __init__(self, model: Optional[str] = None):
        self.client = build_client()
        self.model = (
            model
            or get_env("OPENAI_MODEL")
            or get_env("DEEPSEEK_MODEL")
            or "deepseek-chat"
        )

    def analyze(
        self,
        user_query: str,
        data_payload: Dict[str, Any],
        news_payload: Dict[str, Any],
        knowledge_payload: Dict[str, Any],
        preferences: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        生成最终分析文本

        Args:
            user_query: 用户查询
            data_payload: 数据Agent输出
            news_payload: 新闻Agent输出
            knowledge_payload: 知识Agent输出
            preferences: 用户偏好

        Returns:
            文本建议
        """
        preferences = preferences or {}
        debug_mode = bool(preferences.get("debug_mode", False))

        safe_data_payload = self._sanitize_payload(data_payload)
        safe_news_payload = self._sanitize_payload(news_payload)
        safe_knowledge_payload = self._sanitize_payload(knowledge_payload)

        pref_text = json.dumps(preferences, ensure_ascii=False, default=str)
        data_text = json.dumps(safe_data_payload, ensure_ascii=False, default=str)
        news_text = json.dumps(safe_news_payload, ensure_ascii=False, default=str)
        knowledge_text = json.dumps(safe_knowledge_payload, ensure_ascii=False, default=str)

        if debug_mode:
            system_prompt = (
                "你是投资分析Agent（调试模式）。"
                "请基于给定的数据、新闻和知识库结果生成结论。"
                "输出结构必须包含：摘要、数据要点、新闻与情绪、风险提示、操作建议。"
                "若任一输入缺失，明确标注‘数据缺失原因’，禁止编造。"
                "可附加简短诊断信息。"
                "避免使用确定性收益表述，保留合规风格。"
            )
        else:
            system_prompt = (
                "你是投资分析Agent（使用模式）。"
                "请直接给用户可读的投资分析结论。"
                "输出结构包含：摘要、数据要点、风险提示、操作建议。"
                "若存在缺失，请用‘部分信息暂不可用’等用户友好表述。"
                "不要输出内部异常、错误栈、Agent名称、工具名、JSON字段名或调试信息。"
                "避免使用确定性收益表述，保留合规风格。"
            )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query},
            {"role": "user", "content": f"投资偏好: {pref_text}"},
            {"role": "user", "content": f"数据Agent结果: {data_text}"},
            {"role": "user", "content": f"新闻Agent结果: {news_text}"},
            {"role": "user", "content": f"知识Agent结果: {knowledge_text}"},
        ]

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
        )
        return response.choices[0].message.content or ""

    def _sanitize_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """清理内部调试字段，避免在使用模式中泄露异常细节"""
        blocked_keys = {
            "error",
            "exception",
            "traceback",
            "stack",
            "fallback_reason",
            "tool_call_id",
            "latency_ms",
        }

        def walk(value: Any) -> Any:
            if isinstance(value, dict):
                output: Dict[str, Any] = {}
                for key, item in value.items():
                    if str(key).lower() in blocked_keys:
                        continue
                    output[key] = walk(item)
                return output
            if isinstance(value, list):
                return [walk(item) for item in value]
            return value

        return walk(payload or {})
