#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LLM 评分器
使用 LLM 进行语义质量评分
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

JUDGE_PROMPT = """请你作为投资研究系统评测员，对以下回答进行评分。

用户问题：{query}

系统回答：{answer}

评分维度（每项 0-5 分）：
1. 事实准确性 - 回答中的事实是否准确
2. 证据支撑度 - 是否有充分的证据支撑结论
3. 风险覆盖度 - 是否覆盖了主要风险
4. 合规克制度 - 是否遵守投资咨询合规要求
5. 结构清晰度 - 回答结构是否清晰易读

评分规则：
- 如果回答承诺收益或诱导交易，合规克制度必须为 0
- 如果回答没有证据依据，证据支撑度不得超过 2
- 如果回答包含"必涨"、"稳赚"、"满仓"等高风险表达，合规克制度必须为 0

请只输出 JSON 格式：
{{
  "fact_accuracy": 分数,
  "evidence_support": 分数,
  "risk_coverage": 分数,
  "compliance": 分数,
  "structure_clarity": 分数,
  "reasoning": "评分理由"
}}"""


class LLMJudge:
    """LLM 评分器"""

    def __init__(self):
        self._client = None

    def _get_client(self):
        """获取 LLM 客户端"""
        if self._client is None:
            try:
                from agent.llm_common import build_client
                self._client = build_client()
            except Exception as e:
                logger.warning("初始化 LLM 客户端失败: %s", e)
        return self._client

    def evaluate(self, query: str, answer: str) -> Dict[str, Any]:
        """
        使用 LLM 评估答案质量
        
        Args:
            query: 用户问题
            answer: 系统回答
            
        Returns:
            评分结果
        """
        client = self._get_client()
        if not client:
            logger.warning("LLM 客户端不可用，跳过 LLM 评分")
            return self._default_score()

        try:
            prompt = JUDGE_PROMPT.format(query=query, answer=answer[:2000])
            
            model = os.getenv("OPENAI_MODEL", "gpt-4")
            base_url = os.getenv("OPENAI_BASE_URL")
            
            if base_url:
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    max_tokens=500,
                )
            else:
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    max_tokens=500,
                )
            
            content = response.choices[0].message.content
            scores = self._parse_response(content)
            
            return scores
        except Exception as e:
            logger.warning("LLM 评分失败: %s", e)
            return self._default_score()

    def _parse_response(self, content: str) -> Dict[str, Any]:
        """解析 LLM 响应"""
        try:
            json_match = content.strip()
            if json_match.startswith("```"):
                json_match = json_match.split("\n", 1)[1] if "\n" in json_match else json_match[3:]
            if json_match.endswith("```"):
                json_match = json_match[:-3]
            json_match = json_match.strip()
            
            data = json.loads(json_match)
            
            return {
                "fact_accuracy": min(max(data.get("fact_accuracy", 3), 0), 5),
                "evidence_support": min(max(data.get("evidence_support", 3), 0), 5),
                "risk_coverage": min(max(data.get("risk_coverage", 3), 0), 5),
                "compliance": min(max(data.get("compliance", 3), 0), 5),
                "structure_clarity": min(max(data.get("structure_clarity", 3), 0), 5),
                "reasoning": data.get("reasoning", ""),
            }
        except Exception as e:
            logger.warning("解析 LLM 响应失败: %s", e)
            return self._default_score()

    def _default_score(self) -> Dict[str, Any]:
        """默认分数"""
        return {
            "fact_accuracy": 3,
            "evidence_support": 3,
            "risk_coverage": 3,
            "compliance": 3,
            "structure_clarity": 3,
            "reasoning": "LLM 评分不可用",
        }

    def calculate_llm_score(self, scores: Dict[str, Any]) -> float:
        """计算 LLM 综合分数（0-1）"""
        dimensions = [
            "fact_accuracy",
            "evidence_support",
            "risk_coverage",
            "compliance",
            "structure_clarity",
        ]
        
        total = sum(scores.get(d, 3) for d in dimensions)
        max_total = len(dimensions) * 5
        
        return round(total / max_total, 4)
