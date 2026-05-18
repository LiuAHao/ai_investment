#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
评审节点
检查答案质量，基于证据校验
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

from agent.v2.state import EvidenceItem, EvidenceType, InvestmentState
from services.task_service import TaskService

logger = logging.getLogger(__name__)

CRITIC_THRESHOLD = 0.6


def critic_check(state: InvestmentState) -> Dict[str, Any]:
    """
    评审检查
    
    职责：
    - 检查是否有无证据结论
    - 检查是否遗漏主要风险
    - 检查数据是否过旧
    - 检查是否与用户风险偏好冲突
    """
    logger.info("critic_check: 评审答案")

    draft = state.draft_answer or ""
    evidence = state.evidence_items
    
    score, issues = _evaluate_answer(draft, evidence, state.tool_results)
    needs_revision = score < CRITIC_THRESHOLD

    trace = state.trace + [{
        "node": "critic_check",
        "status": "completed",
        "input_summary": f"draft_length={len(draft)}, evidence={len(evidence)}",
        "output_summary": f"score={score:.2f}, needs_revision={needs_revision}, issues={len(issues)}",
        "latency_ms": 0,
    }]

    TaskService.emit_event(state.task_id, "critic_completed", {
        "passed": not needs_revision,
        "score": int(score * 100),
        "issues": issues,
    })

    return {
        "critic_score": score,
        "critic_issues": issues,
        "trace": trace,
    }


def should_revise(state: InvestmentState) -> str:
    """条件边：是否需要修改答案"""
    if state.critic_score is not None and state.critic_score < CRITIC_THRESHOLD:
        return "revise"
    return "compliance"


def revise_answer(state: InvestmentState) -> Dict[str, Any]:
    """
    修改答案
    
    职责：
    - 根据评审意见修改答案
    - 补充遗漏的风险提示
    - 标记无证据结论
    """
    logger.info("revise_answer: 修改答案")

    draft = state.draft_answer or ""
    issues = state.critic_issues
    
    revised = draft
    
    if "缺少风险提示" in str(issues):
        revised = _add_risk_disclaimer(revised)
    
    if "缺少数据时效性说明" in str(issues):
        revised = _add_freshness_note(revised)
    
    revised = _mark_unsupported_claims(revised, state.evidence_items)

    trace = state.trace + [{
        "node": "revise_answer",
        "status": "completed",
        "input_summary": f"original_length={len(draft)}, issues={len(issues)}",
        "output_summary": f"revised_length={len(revised)}",
        "latency_ms": 0,
    }]

    return {
        "draft_answer": revised,
        "trace": trace,
    }


def _evaluate_answer(draft: str, evidence: List[EvidenceItem], tool_results: list) -> tuple:
    """评估答案质量"""
    if not draft:
        return 0.0, ["答案为空"]

    issues = []
    score = 0.5

    if len(draft) > 100:
        score += 0.1
    if len(draft) > 300:
        score += 0.1

    has_data = any(
        r.status in ("success", "partial") and r.tool_name in ("cn_stock_history", "us_stock_history", "analysis")
        for r in tool_results
    )
    if has_data:
        score += 0.1

    if evidence:
        score += 0.1
    else:
        issues.append("缺少证据支撑")

    risk_keywords = ["风险", "注意", "谨慎", "仅供参考", "不构成"]
    if any(kw in draft for kw in risk_keywords):
        score += 0.1
    else:
        issues.append("缺少风险提示")

    unsupported = _check_unsupported_claims(draft, evidence)
    if unsupported:
        issues.extend(unsupported)
        score -= 0.1 * len(unsupported)

    freshness_issues = _check_freshness(draft, evidence)
    if freshness_issues:
        issues.extend(freshness_issues)
        score -= 0.05

    return max(min(score, 1.0), 0.0), issues


def _check_unsupported_claims(draft: str, evidence: List[EvidenceItem]) -> List[str]:
    """检查无证据结论"""
    issues = []
    
    claim_patterns = [
        (r"将会.*上涨", "预测上涨"),
        (r"必定.*跌", "预测下跌"),
        (r"肯定.*收益", "承诺收益"),
        (r"目标价.*\d+", "目标价"),
    ]
    
    for pattern, claim_type in claim_patterns:
        if re.search(pattern, draft):
            if not _has_supporting_evidence(claim_type, evidence):
                issues.append(f"无证据结论: {claim_type}")
    
    return issues


def _has_supporting_evidence(claim_type: str, evidence: List[EvidenceItem]) -> bool:
    """检查是否有支撑证据"""
    if claim_type in ("预测上涨", "预测下跌"):
        return any(e.evidence_type in (EvidenceType.MARKET_DATA, EvidenceType.TECHNICAL_INDICATOR) for e in evidence)
    elif claim_type == "承诺收益":
        return False
    elif claim_type == "目标价":
        return any(e.evidence_type == EvidenceType.FUNDAMENTAL for e in evidence)
    return False


def _check_freshness(draft: str, evidence: List[EvidenceItem]) -> List[str]:
    """检查数据新鲜度"""
    issues = []
    
    old_evidence = [e for e in evidence if e.observed_at]
    if old_evidence:
        from datetime import datetime
        now = datetime.now()
        for e in old_evidence:
            try:
                age_days = (now - e.observed_at).days
                if age_days > 7:
                    issues.append(f"数据过旧: {e.title}")
            except Exception:
                pass
    
    return issues[:3]


def _add_risk_disclaimer(draft: str) -> str:
    """添加风险声明"""
    disclaimer = "\n\n**风险提示：** 以上分析基于公开数据，仅供参考，不构成投资建议。投资有风险，决策需谨慎。"
    if "风险" not in draft and "仅供参考" not in draft:
        return draft + disclaimer
    return draft


def _add_freshness_note(draft: str) -> str:
    """添加数据时效性说明"""
    note = "\n\n**数据时效：** 上述数据基于最近可获取的公开信息，市场状况可能已发生变化。"
    if "时效" not in draft and "数据时间" not in draft:
        return draft + note
    return draft


def _mark_unsupported_claims(draft: str, evidence: List[EvidenceItem]) -> str:
    """标记无证据结论"""
    if not evidence:
        return draft
    
    if re.search(r"将会.*上涨", draft) and not any(e.evidence_type == EvidenceType.TECHNICAL_INDICATOR for e in evidence):
        draft = re.sub(r"(将会.*上涨)", r"\1（需更多技术面确认）", draft)
    
    return draft
