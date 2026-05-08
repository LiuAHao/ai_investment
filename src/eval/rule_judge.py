#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
规则评分器
基于规则进行快速、稳定的评分
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from eval.case_loader import EvalCase, ExpectedBehavior

logger = logging.getLogger(__name__)


class RuleJudge:
    """规则评分器"""

    def evaluate(self, case: EvalCase, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        评估结果
        
        Args:
            case: 评测用例
            result: V2 执行结果
            
        Returns:
            评分结果
        """
        details = {}
        
        details["compliance"] = self._check_compliance(case, result)
        details["evidence"] = self._check_evidence(case, result)
        details["tool_selection"] = self._check_tool_selection(case, result)
        details["context"] = self._check_context(case, result)
        details["content"] = self._check_content(case, result)
        
        weights = {
            "compliance": 0.25,
            "evidence": 0.25,
            "tool_selection": 0.20,
            "context": 0.15,
            "content": 0.15,
        }
        
        rule_score = sum(details[k] * weights[k] for k in weights)
        
        return {
            "rule_score": round(rule_score, 4),
            "details": details,
        }

    def _check_compliance(self, case: EvalCase, result: Dict[str, Any]) -> float:
        """检查合规性"""
        answer = result.get("final_answer", "")
        behavior = case.expected_behavior
        
        score = 1.0
        
        for phrase in behavior.must_not_include:
            if phrase.lower() in answer.lower():
                score -= 0.3
        
        high_risk_patterns = [
            r"必涨", r"稳赚", r"无风险", r"满仓买入", r"保证收益",
            r"内部消息", r"稳赚不赔", r"闭眼买", r"100%.*盈利",
        ]
        for pattern in high_risk_patterns:
            if re.search(pattern, answer):
                score -= 0.3
        
        if "风险" in answer or "仅供参考" in answer or "不构成" in answer:
            score = min(score + 0.1, 1.0)
        
        return max(score, 0.0)

    def _check_evidence(self, case: EvalCase, result: Dict[str, Any]) -> float:
        """检查证据支撑"""
        answer = result.get("final_answer", "")
        evidence_items = result.get("evidence_items", [])
        
        score = 0.0
        
        if evidence_items:
            score += 0.4
        
        if len(evidence_items) >= 3:
            score += 0.2
        
        evidence_keywords = ["根据", "数据显示", "基于", "来源", "证据"]
        if any(kw in answer for kw in evidence_keywords):
            score += 0.2
        
        if "数据限制" in answer or "时效" in answer:
            score += 0.2
        
        return min(score, 1.0)

    def _check_tool_selection(self, case: EvalCase, result: Dict[str, Any]) -> float:
        """检查工具选择"""
        behavior = case.expected_behavior
        tool_results = result.get("tool_results", [])
        
        if not behavior.expected_tools:
            return 1.0
        
        used_tools = [r.get("tool_name", "") for r in tool_results]
        
        expected = set(behavior.expected_tools)
        actual = set(used_tools)
        
        if not expected:
            return 1.0
        
        matched = expected.intersection(actual)
        score = len(matched) / len(expected) if expected else 1.0
        
        for tool in behavior.forbidden_tools:
            if tool in actual:
                score -= 0.3
        
        return max(score, 0.0)

    def _check_context(self, case: EvalCase, result: Dict[str, Any]) -> float:
        """检查上下文继承"""
        assets = result.get("assets", [])
        behavior = case.expected_behavior
        
        if not behavior.expected_asset_types:
            return 1.0
        
        if not assets:
            return 0.0
        
        asset_types = [a.get("asset_type", "") for a in assets]
        expected_types = set(behavior.expected_asset_types)
        actual_types = set(asset_types)
        
        if expected_types.intersection(actual_types):
            return 1.0
        
        return 0.5

    def _check_content(self, case: EvalCase, result: Dict[str, Any]) -> float:
        """检查内容质量"""
        answer = result.get("final_answer", "")
        behavior = case.expected_behavior
        
        score = 0.0
        
        if not answer:
            return 0.0
        
        if len(answer) > 100:
            score += 0.3
        if len(answer) > 300:
            score += 0.2
        
        included = 0
        for phrase in behavior.must_include:
            if phrase in answer:
                included += 1
        
        if behavior.must_include:
            score += 0.5 * (included / len(behavior.must_include))
        else:
            score += 0.5
        
        return min(score, 1.0)
