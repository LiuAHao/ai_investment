#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
裁判（Adjudicator）

两段调用，刻意分开：
1. Blind：只看证据台账 + 两份匿名论点（去 side 标签、顺序随机）
2. Final：读完整辩论后裁决，必须写清"被哪条攻击改变、为什么"

盲判结果留档（blind_stance / blind_conviction），用于事后校准裁判是否被辩论带偏。
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from agents.ledger import EvidenceLedger
from agents.state import DebateTurn, Disagreement, Thesis, Verdict

logger = logging.getLogger(__name__)

STANCES = ("bullish", "neutral", "bearish")


class Judge:
    """投资裁决"""

    def __init__(self, llm: Any, ledger: EvidenceLedger, task_id: str = ""):
        self.llm = llm
        self.ledger = ledger
        self.task_id = task_id

    # ---------- 盲判 ----------

    def blind(
        self,
        query: str,
        bull: Thesis,
        bear: Thesis,
        focus_questions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        匿名盲判：不告诉模型哪份是多/空，去除已有倾向。
        """
        # 用 query 哈希决定顺序，保证同一问题可复现
        flip = sum(ord(ch) for ch in query) % 2 == 1
        first, second = (bear, bull) if flip else (bull, bear)
        mapping = {"A": first.side, "B": second.side}

        system = (
            "你是投资委员会主席。你现在只做独立判断，不参与辩论。\n"
            "你会看到两份匿名论点（A/B）和同一份证据台账。不要猜测哪份来自哪一方。\n"
            "要求：\n"
            "1. 只能基于证据台账下判断，不得引入台账外事实。\n"
            "2. key_drivers 的每条必须标注支撑它的 evidence_id。\n"
            "3. 若关键数据缺失导致无法判断，stance 仍要给出，但在 uncertainties 中说明。\n"
            "只输出 JSON。"
        )
        user = (
            f"研究问题：{query}\n"
            f"需要回答的问题：{focus_questions or []}\n\n"
            f"证据台账：\n{self.ledger.format_for_prompt(limit_per_category=15)}\n\n"
            f"论点 A：\n{_format_thesis(first)}\n\n"
            f"论点 B：\n{_format_thesis(second)}\n\n"
            "输出 JSON：{\"stance\":\"bullish|neutral|bearish\",\"conviction\":0.0,"
            "\"key_drivers\":[{\"text\":\"...\",\"evidence_id\":\"EV-0001\"}],"
            "\"uncertainties\":[\"...\"]}"
        )
        data = self.llm.json(system, user, max_tokens=3000, required_keys=["stance"])
        if not data:
            return {
                "stance": "neutral", "conviction": 0.3, "key_drivers": [],
                "uncertainties": ["盲判失败"], "mapping": {},
            }
        stance = str(data.get("stance") or "neutral").lower()
        if stance not in STANCES:
            stance = "neutral"
        drivers = []
        for item in data.get("key_drivers") or []:
            if isinstance(item, dict):
                text = str(item.get("text") or "").strip()
                eid = str(item.get("evidence_id") or "").strip()
                if text:
                    drivers.append(f"{text}（{eid}）" if eid else text)
            elif isinstance(item, str) and item.strip():
                drivers.append(item.strip())
        return {
            "stance": stance,
            "conviction": _clamp(data.get("conviction"), 0.3),
            "key_drivers": drivers,
            "uncertainties": [str(x) for x in (data.get("uncertainties") or []) if x],
            "mapping": mapping,
        }

    # ---------- 终判 ----------

    def final(
        self,
        query: str,
        bull: Thesis,
        bear: Thesis,
        blind: Dict[str, Any],
        turns: Optional[List[DebateTurn]] = None,
        focus_questions: Optional[List[str]] = None,
        horizon: str = "medium",
        debate_enabled: bool = True,
        issues: Optional[List[str]] = None,
    ) -> Verdict:
        turns = turns or []
        issue_block = ""
        if issues:
            issue_block = (
                "\n上一版裁决未通过质检，请修正以下问题后重新输出：\n"
                + "\n".join(f"- {issue}" for issue in issues[:10])
                + "\n修正时必须删除或弱化无法被证据支持的内容，不得只改措辞。\n"
            )
        system = (
            "你是投资委员会主席，现在需要给出最终裁决。\n"
            "硬性要求：\n"
            "1. 只能引用证据台账中的 evidence_id，不得引入新事实。\n"
            "2. 最终判断可以与盲判不同，但必须写 revision_reason：哪条攻击/让步改变了判断、为什么。\n"
            "   若判断未变，说明辩论为何没有提供新信息。\n"
            "3. 不得因为双方'都有道理'就默认中性。中性必须区分'证据真对冲'与'关键数据缺失'。\n"
            "4. position_hint 只允许写仓位区间（如 '10%-20% 试探仓位'），不得写买卖指令或目标价。\n"
            "5. disagreement_map 必须列出双方真实分歧，不要写成'双方各有道理'。\n"
            "只输出 JSON。"
        )
        user = (
            f"研究问题：{query}\n"
            f"时间框架：{horizon}\n"
            f"需要回答的问题：{focus_questions or []}\n\n"
            f"证据台账：\n{self.ledger.format_for_prompt(limit_per_category=15)}\n\n"
            f"多方论点：\n{_format_thesis(bull)}\n\n"
            f"空方论点：\n{_format_thesis(bear)}\n\n"
            f"你的盲判（匿名阶段）：\n"
            f"{json.dumps({k: v for k, v in blind.items() if k != 'mapping'}, ensure_ascii=False)}\n\n"
            f"辩论记录：\n{_format_turns(turns) if turns else '（本次未启用辩论）'}\n"
            f"{issue_block}\n"
            "输出 JSON：\n"
            "{\n"
            "  \"stance\": \"bullish|neutral|bearish\",\n"
            "  \"conviction\": 0.0,\n"
            "  \"summary\": \"3-5 句核心逻辑链\",\n"
            "  \"key_drivers\": [\"...（EV-0001）\"],\n"
            "  \"disagreement_map\": [{\"topic\":\"...\",\"bull_view\":\"...\",\"bear_view\":\"...\","
            "\"resolvable\":\"yes|no|needs_data\",\"resolution\":\"...\"}],\n"
            "  \"falsifiers_to_watch\": [\"未来可观察的否证信号\"],\n"
            "  \"what_would_change_my_mind\": [\"...\"],\n"
            "  \"position_hint\": \"仓位区间\",\n"
            "  \"time_frame\": \"...\",\n"
            "  \"structured_risks\": [{\"type\":\"市场/行业/财务/政策/流动性/技术\",\"desc\":\"...\","
            "\"probability\":\"high|medium|low\",\"impact\":\"high|medium|low\",\"priced_in\":true}],\n"
            "  \"revision_reason\": \"...\",\n"
            "  \"confidence_calibration\": \"本判断最可能错在哪\",\n"
            "  \"evidence_ids\": [\"EV-0001\"]\n"
            "}"
        )
        data = self.llm.json(system, user, max_tokens=8000, required_keys=["stance", "conviction"])
        if not data:
            data = {}

        stance = str(data.get("stance") or blind.get("stance") or "neutral").lower()
        if stance not in STANCES:
            stance = "neutral"

        evidence_ids = [str(x) for x in (data.get("evidence_ids") or []) if x]
        for claim in list(bull.claims) + list(bear.claims):
            for eid in claim.evidence_ids:
                if eid not in evidence_ids:
                    evidence_ids.append(eid)

        disagreements: List[Disagreement] = []
        for raw in data.get("disagreement_map") or []:
            if not isinstance(raw, dict):
                continue
            topic = str(raw.get("topic") or "").strip()
            if not topic:
                continue
            resolvable = str(raw.get("resolvable") or "needs_data").lower()
            if resolvable not in ("yes", "no", "needs_data"):
                resolvable = "needs_data"
            disagreements.append(Disagreement(
                topic=topic,
                bull_view=str(raw.get("bull_view") or ""),
                bear_view=str(raw.get("bear_view") or ""),
                resolvable=resolvable,  # type: ignore[arg-type]
                resolution=str(raw.get("resolution") or ""),
            ))

        revision_reason = str(data.get("revision_reason") or "").strip()
        if not revision_reason:
            revision_reason = "未启用辩论" if not debate_enabled else "模型未说明修订理由"

        return Verdict(
            stance=stance,  # type: ignore[arg-type]
            conviction=_clamp(data.get("conviction"), 0.5),
            summary=str(data.get("summary") or ""),
            key_drivers=[str(x) for x in (data.get("key_drivers") or []) if x],
            disagreement_map=disagreements,
            falsifiers_to_watch=[str(x) for x in (data.get("falsifiers_to_watch") or []) if x],
            what_would_change_my_mind=[
                str(x) for x in (data.get("what_would_change_my_mind") or []) if x
            ],
            position_hint=str(data.get("position_hint") or ""),
            time_frame=str(data.get("time_frame") or horizon),
            structured_risks=_parse_risks(data.get("structured_risks")),
            blind_stance=str(blind.get("stance") or ""),
            blind_conviction=_clamp(blind.get("conviction"), 0.0),
            revision_reason=revision_reason,
            confidence_calibration=str(data.get("confidence_calibration") or ""),
            evidence_ids=evidence_ids,
        )


# ---------- 辅助 ----------

def _clamp(value: Any, default: float) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def _parse_risks(raw: Any) -> List[Dict[str, Any]]:
    risks: List[Dict[str, Any]] = []
    if not isinstance(raw, list):
        return risks
    for item in raw:
        if not isinstance(item, dict):
            continue
        desc = str(item.get("desc") or item.get("description") or "").strip()
        if not desc:
            continue
        probability = str(item.get("probability") or "medium").lower()
        impact = str(item.get("impact") or "medium").lower()
        risks.append({
            "type": str(item.get("type") or "其他"),
            "desc": desc,
            "probability": probability if probability in ("high", "medium", "low") else "medium",
            "impact": impact if impact in ("high", "medium", "low") else "medium",
            "priced_in": item.get("priced_in"),
        })
    return risks


def _format_thesis(thesis: Thesis) -> str:
    payload = {
        "core_claim": thesis.core_claim,
        "confidence": thesis.confidence,
        "claims": [
            {
                "claim_id": c.claim_id,
                "statement": c.statement,
                "strength": c.strength,
                "evidence_ids": c.evidence_ids,
                "assumptions": c.assumptions,
                "falsifiers": c.falsifiers,
            }
            for c in thesis.claims
        ],
        "kill_criteria": thesis.kill_criteria,
        "unanswered_gaps": thesis.unanswered_gaps,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _format_turns(turns: List[DebateTurn]) -> str:
    lines = []
    for turn in turns:
        part = f"[R{turn.round}|{turn.side}|{turn.action}]"
        if turn.target_claim_id:
            part += f" target={turn.target_claim_id}"
        if turn.attack_type:
            part += f" type={turn.attack_type}"
        part += f" {turn.argument}"
        if turn.concession:
            part += f" | 让步: {turn.concession}"
        if turn.no_concession_reason:
            part += f" | 零让步理由: {turn.no_concession_reason}"
        lines.append(part)
    return "\n".join(lines) or "（无）"
