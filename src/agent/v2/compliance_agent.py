#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
合规检查节点
检查答案的合规性，包含 Prompt 注入防护
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

from agent.v2.state import InvestmentState

logger = logging.getLogger(__name__)

BLOCKED_PATTERNS = [
    r"保证.*收益",
    r"稳赚.*不赔",
    r"内幕.*消息",
    r"内部.*消息",
    r"涨停.*板.*买入",
    r"无风险.*高收益",
    r"100%.*盈利",
    r"必涨",
    r"稳赚",
    r"满仓买入",
    r"闭眼买",
    r"无风险",
]

INJECTION_PATTERNS = [
    r"ignore.*previous.*instructions",
    r"忽略.*之前.*指令",
    r"忽略.*所有.*规则",
    r"system.*prompt",
    r"你的指令是",
    r"假装.*你是",
    r"忽略.*系统",
    r"不要.*遵循",
    r"绕过.*限制",
    r"忽略.*以上",
]


def compliance_check(state: InvestmentState) -> Dict[str, Any]:
    """
    合规检查
    
    职责：
    - 检查合规表达
    - 检查高风险建议
    - 检查 Prompt 注入痕迹
    - 检查外部文本中的注入
    """
    logger.info("compliance_check: 合规检查")

    draft = state.draft_answer or ""
    query = state.query
    passed = True
    issues: List[str] = []

    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, draft):
            issues.append(f"包含高风险表述: {pattern}")
            passed = False

    if _detect_high_risk_advice_request(query):
        issues.append("用户请求包含高风险投资指令")
        passed = False

    if _detect_injection(query):
        issues.append("检测到可能的 Prompt 注入")
        passed = False

    if _detect_injection_in_text(draft):
        issues.append("答案中包含可疑指令")
        passed = False

    external_injection_found = False
    for result in state.tool_results:
        if result.status in ("success", "partial"):
            data_str = str(result.data)
            if _detect_injection_in_text(data_str):
                issues.append(f"工具 {result.tool_name} 返回的外部文本可能包含注入")
                external_injection_found = True
                break

    final_answer = state.final_answer
    if external_injection_found and final_answer:
        final_answer = (
            final_answer
            + "\n\n**安全提示**\n部分外部文本包含疑似指令注入内容，系统已将其仅作为非可信数据处理。"
        )

    trace = state.trace + [{
        "node": "compliance_check",
        "status": "completed",
        "input_summary": f"draft_length={len(draft)}",
        "output_summary": f"passed={passed}, issues={len(issues)}",
        "latency_ms": 0,
    }]

    output = {
        "compliance_passed": passed,
        "errors": state.errors + issues,
        "trace": trace,
    }
    if final_answer is not None:
        output["final_answer"] = final_answer
    return output


def should_block(state: InvestmentState) -> str:
    """条件边：是否需要阻止答案"""
    if not state.compliance_passed:
        return "block"
    return "final"


def safe_response(state: InvestmentState) -> Dict[str, Any]:
    """
    安全响应
    
    当合规检查失败时生成安全答案
    """
    logger.info("safe_response: 生成安全响应")

    has_injection = any("注入" in e for e in state.errors)
    
    if has_injection:
        safe_answer = (
            "抱歉，您的输入中包含可能不安全的内容，我无法处理该请求。\n\n"
            "如果您有投资相关问题，请重新描述。\n\n"
            "**投资有风险，入市需谨慎。**"
        )
    else:
        safe_answer = (
            "抱歉，我无法对该问题提供具体的投资建议。\n\n"
            "如果您需要投资建议，建议：\n"
            "1. 咨询持牌金融机构\n"
            "2. 参考官方发布的市场信息\n"
            "3. 根据自身风险承受能力做出决策\n\n"
            "**投资有风险，入市需谨慎。**"
        )

    trace = state.trace + [{
        "node": "safe_response",
        "status": "completed",
        "input_summary": "compliance failed",
        "output_summary": "safe response generated",
        "latency_ms": 0,
    }]

    return {
        "final_answer": safe_answer,
        "trace": trace,
    }


def _detect_injection(query: str) -> bool:
    """检测 Prompt 注入"""
    query_lower = query.lower()
    return any(re.search(p, query_lower) for p in INJECTION_PATTERNS)


def _detect_high_risk_advice_request(query: str) -> bool:
    """检测用户是否在请求高风险确定性交易指令"""
    if not query:
        return False

    high_risk_request_patterns = [
        r"必涨",
        r"稳赚",
        r"保证.*收益",
        r"稳赚.*不赔",
        r"满仓.*买",
        r"闭眼.*买",
        r"无风险.*收益",
        r"内部.*消息",
        r"内幕.*消息",
    ]
    return any(re.search(pattern, query) for pattern in high_risk_request_patterns)


def _detect_injection_in_text(text: str) -> bool:
    """检测文本中的 Prompt 注入"""
    if not text:
        return False
    
    text_lower = text.lower()
    
    injection_phrases = [
        "忽略所有规则",
        "忽略之前指令",
        "ignore previous",
        "ignore all rules",
        "你是系统",
        "你的指令是",
        "假装你是",
        "绕过限制",
    ]
    
    for phrase in injection_phrases:
        if phrase in text_lower:
            return True
    
    return False


def sanitize_external_text(text: str) -> str:
    """
    清洗外部文本
    
    将外部文本标记为数据而非指令
    """
    if not text:
        return ""
    
    sanitized = text.replace("{", "\\{").replace("}", "\\}")
    
    return sanitized
