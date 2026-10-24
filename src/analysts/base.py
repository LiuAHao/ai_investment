#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
分析师基类与输出契约

分析师只交证据，不下结论。结论由 Bull/Bear 论点与 Judge 裁决产生。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from agents.base import BaseReActAgent
from agents.llm import extract_json_object

EVIDENCE_CONTRACT = """【输出契约·必须】
只输出事实性证据，不得输出"看多/看空/建议买入/目标价"等结论。
最终以 JSON 输出（decision=final），结构如下：
{
  "decision": "final",
  "highlights": [
    {"category": "market|valuation|technical|fundamental|news|announcement|macro|policy",
     "statement": "一句话事实，含具体数值与对象",
     "value": 数值或null,
     "unit": "单位，如 % / 倍 / 元",
     "caliber": "口径，如 PE(TTM)/前复权/单季",
     "source_time": "数据时间 YYYY-MM-DD"}
  ],
  "gaps": [{"question": "未能回答的问题", "reason": "缺少什么数据或工具"}],
  "coverage": {"asked": 问题数, "answered": 已答数, "failed": 失败数}
}

【硬性规则】
1. highlights 最多 3 条，只放"工具没直接给出、但由工具数据推导出的关键事实"；
   工具返回的原始数据已由系统自动登记，**不要复述**。
2. 每条 highlight 必须来自工具返回的真实数据，不得编造数字。
3. 无法回答的问题写入 gaps，不要用推测填补。
4. 同一指标只用一个口径；跨口径对比必须显式说明。
5. 工具失败时记录到 gaps，同一工具最多重试 2 次。
6. 证据充分后立即收敛，不要为调用而调用。
7. 工具调用回合不要输出长篇推理；需要思考就直接调用工具，最终结论时才输出 JSON。
8. 顶层只允许 highlights / gaps / coverage 三个字段，禁止输出评述、结论、反问用户的句子。
9. 禁止输出"需要我进一步…吗""是否要我…"这类对话式内容。

【取证优先级】
{questions}
"""


class BaseAnalyst(BaseReActAgent):
    """所有分析师的公共基类"""

    stage = "L1"
    evidence_category = "market"
    max_iterations = 4
    max_tokens = 4096
    keep_full_json = True
    final_instruction = (
        "只输出一个 JSON 对象（不要代码块、不要解释），必须包含 "
        "decision=\"final\" 与 evidence/gaps/coverage 三个字段"
    )

    def _build_prompt(self, task: Any) -> str:
        # 注意：EVIDENCE_CONTRACT 内含 JSON 大括号，不能用 str.format（会被当作占位符）
        return f"{self.system_prompt}\n\n{EVIDENCE_CONTRACT.replace('{questions}', self._questions_hint(task))}"

    def _questions_hint(self, task: Any) -> str:
        questions = getattr(task, "focus_questions", None) or []
        if not questions:
            return "按角色职责覆盖核心维度"
        return "\n".join(f"- {q}" for q in questions)


def parse_analyst_payload(
    conclusion: str,
    analyst: str,
    default_category: str,
    allowed_tools: List[str],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]], Dict[str, Any]]:
    """
    解析分析师最终输出。

    Returns:
        (evidence_raw, gaps, coverage)
    """
    data = extract_json_object(conclusion) or {}
    evidence: List[Dict[str, Any]] = []
    raw_items = data.get("highlights") if isinstance(data.get("highlights"), list) else data.get("evidence")
    for raw in raw_items or []:
        if not isinstance(raw, dict):
            continue
        statement = str(raw.get("statement") or "").strip()
        if not statement:
            continue
        category = str(raw.get("category") or default_category).strip().lower()
        if category == "price":
            category = "market"
        if category not in (
            "market", "valuation", "technical", "fundamental",
            "news", "announcement", "macro", "policy", "flow",
        ):
            category = default_category
        source_tool = str(raw.get("source_tool") or "").strip()
        if not source_tool:
            source_tool = "llm_extracted"
        elif source_tool not in allowed_tools:
            source_tool = "llm_extracted"
        evidence.append({
            "category": category,
            "statement": statement[:500],
            "value": raw.get("value"),
            "unit": str(raw.get("unit") or ""),
            "caliber": str(raw.get("caliber") or ""),
            "source_tool": source_tool,
            "source_time": str(raw.get("source_time") or ""),
            "confidence": _clamp(raw.get("confidence"), 0.75),
        })

    gaps: List[Dict[str, str]] = []
    for raw in data.get("gaps") or []:
        if isinstance(raw, dict):
            question = str(raw.get("question") or raw.get("gap") or "").strip()
            if question:
                gaps.append({"question": question, "reason": str(raw.get("reason") or "")})
        elif isinstance(raw, str) and raw.strip():
            gaps.append({"question": raw.strip(), "reason": ""})

    coverage = data.get("coverage") if isinstance(data.get("coverage"), dict) else {}

    # 模型未按契约输出时兜底：把结论文本作为一条低置信证据
    if not evidence and conclusion.strip():
        text = _strip_json(conclusion)
        if text:
            evidence.append({
                "category": default_category,
                "statement": text[:400],
                "value": None,
                "unit": "",
                "caliber": "",
                "source_tool": "llm_extracted",
                "source_time": "",
                "confidence": 0.45,
            })
            gaps.append({"question": "结构化证据解析失败", "reason": "模型输出未遵循 JSON 契约"})

    return evidence, gaps, coverage


def _clamp(value: Any, default: float) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def _strip_json(text: str) -> str:
    """若文本是 JSON，取 summary/conclusion；否则返回原文前 400 字"""
    candidate = text.strip()
    if candidate.startswith("{"):
        data = extract_json_object(candidate)
        if data:
            return str(data.get("summary") or data.get("conclusion") or "").strip()
        return ""
    return re.sub(r"\s+", " ", candidate)[:400]
