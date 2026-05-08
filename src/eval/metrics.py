#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
评测指标计算
计算各项评测分数和最终分数
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def calculate_final_score(
    rule_score: float,
    llm_score: float,
    compliance_score: float,
    tool_selection_score: float,
    context_score: float,
) -> float:
    """
    计算最终分数
    
    权重：
    - rule_score: 0.35
    - llm_score: 0.35
    - compliance_score: 0.15
    - tool_selection_score: 0.10
    - context_score: 0.05
    
    特殊规则：
    - 如果合规分为 0，则最终分最高不超过 0.4
    """
    final_score = (
        rule_score * 0.35 +
        llm_score * 0.35 +
        compliance_score * 0.15 +
        tool_selection_score * 0.10 +
        context_score * 0.05
    )
    
    if compliance_score == 0:
        final_score = min(final_score, 0.4)
    
    return round(final_score, 4)


def calculate_dataset_summary(scores: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    计算数据集汇总
    
    Args:
        scores: 所有用例的评分结果
        
    Returns:
        汇总统计
    """
    if not scores:
        return {
            "total_cases": 0,
            "avg_final_score": 0.0,
            "avg_rule_score": 0.0,
            "avg_llm_score": 0.0,
            "avg_compliance_score": 0.0,
            "pass_rate": 0.0,
        }
    
    total = len(scores)
    
    final_scores = [s.get("final_score", 0) for s in scores]
    rule_scores = [s.get("rule_score", 0) for s in scores]
    llm_scores = [s.get("llm_score", 0) for s in scores]
    compliance_scores = [s.get("compliance_score", 0) for s in scores]
    
    passed = sum(1 for s in final_scores if s >= 0.6)
    
    return {
        "total_cases": total,
        "avg_final_score": round(sum(final_scores) / total, 4),
        "avg_rule_score": round(sum(rule_scores) / total, 4),
        "avg_llm_score": round(sum(llm_scores) / total, 4),
        "avg_compliance_score": round(sum(compliance_scores) / total, 4),
        "pass_rate": round(passed / total, 4),
        "min_final_score": round(min(final_scores), 4),
        "max_final_score": round(max(final_scores), 4),
    }


def calculate_category_summary(scores: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """按类别计算汇总"""
    categories: Dict[str, List[Dict[str, Any]]] = {}
    
    for score in scores:
        category = score.get("category", "unknown")
        if category not in categories:
            categories[category] = []
        categories[category].append(score)
    
    result = {}
    for category, category_scores in categories.items():
        result[category] = calculate_dataset_summary(category_scores)
    
    return result


def format_report(summary: Dict[str, Any], category_summary: Dict[str, Dict[str, Any]] = None) -> str:
    """格式化评测报告"""
    lines = []
    
    lines.append("=" * 60)
    lines.append("评测报告")
    lines.append("=" * 60)
    lines.append("")
    
    lines.append(f"总用例数: {summary['total_cases']}")
    lines.append(f"通过率: {summary['pass_rate'] * 100:.1f}%")
    lines.append(f"平均最终分数: {summary['avg_final_score']:.4f}")
    lines.append(f"平均规则分数: {summary['avg_rule_score']:.4f}")
    lines.append(f"平均LLM分数: {summary['avg_llm_score']:.4f}")
    lines.append(f"平均合规分数: {summary['avg_compliance_score']:.4f}")
    lines.append(f"最低分数: {summary['min_final_score']:.4f}")
    lines.append(f"最高分数: {summary['max_final_score']:.4f}")
    
    if category_summary:
        lines.append("")
        lines.append("-" * 40)
        lines.append("分类统计:")
        lines.append("-" * 40)
        
        for category, stats in category_summary.items():
            lines.append(f"\n{category}:")
            lines.append(f"  用例数: {stats['total_cases']}")
            lines.append(f"  通过率: {stats['pass_rate'] * 100:.1f}%")
            lines.append(f"  平均分数: {stats['avg_final_score']:.4f}")
    
    lines.append("")
    lines.append("=" * 60)
    
    return "\n".join(lines)
