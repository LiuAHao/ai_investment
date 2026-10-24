#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
结构化辩论

不是自由聊天，而是固定格式的对抗动作：
- R1 Attack：只能攻击对方最强的 2 条 claim，攻击类型限定六类
- R2 Answer：每条被攻击的 claim 必须 defend / revise / concede 三选一
- 整轮零让步必须给出理由，并会被下游额外核查
- 全程不得引入台账外事实
"""

from __future__ import annotations

import json
import concurrent.futures as cf
import logging
from typing import Any, Dict, List, Optional

from agents.ledger import EvidenceLedger
from agents.state import Claim, DebateTurn, Thesis

logger = logging.getLogger(__name__)

ATTACK_TYPES = {
    "evidence_gap": "该论点缺少关键证据",
    "logic": "从证据到结论的推理不成立",
    "caliber": "口径混用或不可比",
    "timing": "结论与时间框架不匹配",
    "base_rate": "忽略基础概率或行业常态",
    "priced_in": "已被市场定价",
}

SIDE_LABEL = {"bull": "多方", "bear": "空方"}


class Debater:
    """多空论点构建与辩论执行"""

    def __init__(
        self,
        llm: Any,
        ledger: EvidenceLedger,
        task_id: str = "",
    ):
        self.llm = llm
        self.ledger = ledger
        self.task_id = task_id

    # ---------- 建论 ----------

    def build_thesis(
        self,
        side: str,
        query: str,
        assets: List[Any],
        horizon: str = "medium",
        focus_questions: Optional[List[str]] = None,
        reflections: str = "",
    ) -> Thesis:
        label = SIDE_LABEL.get(side, side)
        system = (
            f"你是{label}研究员。你的任务是构建可被证伪的{label}论点，不是写宣传稿。\n"
            "硬性规则：\n"
            "1. 每条 claim 必须引用证据台账中的 evidence_id（至少 1 个），不得引用台账外的数字或事实。\n"
            "2. 每条 claim 必须给出可观测的 falsifiers（否证条件），不能写'如果基本面恶化'这种空话。\n"
            "3. strength 只能取 high/medium/low；high 表示证据充分且推理链完整。\n"
            "4. claims 控制在 2-4 条，每条 statement 不超过 60 字，reasoning 不超过 80 字，保持紧凑。\n"
            "5. 证据不足时，如实写入 unanswered_gaps，不要用推测补齐。\n"
            "6. 禁止输出'必须买入'之类的确定性指令。\n"
            "只输出 JSON。"
        )
        user = (
            f"研究问题：{query}\n"
            f"资产：{', '.join(str(getattr(a, 'name', '') or getattr(a, 'symbol', '')) for a in assets) or '宏观/市场'}\n"
            f"时间框架：{horizon}\n"
            f"需要回答的问题：{focus_questions or []}\n\n"
            f"证据台账（只能引用这里的 evidence_id）：\n{self.ledger.format_for_prompt(limit_per_category=15)}\n\n"
            + (f"历史决策反思（仅供参考）：\n{reflections}\n\n" if reflections else "")
            + "输出 JSON：\n"
            "{\n"
            f"  \"side\": \"{side}\",\n"
            "  \"core_claim\": \"一句话核心论点\",\n"
            "  \"claims\": [{\"claim_id\": \"CLM-01\", \"statement\": \"...\", \"evidence_ids\": [\"EV-0001\"],\n"
            "               \"reasoning\": \"...\", \"strength\": \"high|medium|low\",\n"
            "               \"assumptions\": [\"...\"], \"falsifiers\": [\"...\"], \"time_horizon\": \"...\"}],\n"
            "  \"key_assumptions\": [\"...\"],\n"
            "  \"kill_criteria\": [\"什么情况下本论点整体失效\"],\n"
            "  \"confidence\": 0.0,\n"
            "  \"unanswered_gaps\": [\"...\"]\n"
            "}"
        )
        data = self.llm.json(system, user, max_tokens=8000, required_keys=["claims"])
        if not data:
            # reasoning 模型可能把输出预算耗在思考上，再给一次机会
            data = self.llm.json(system, user, max_tokens=8000, required_keys=["claims"], temperature=0.1)
        if not data:
            return Thesis(side=side, confidence=0.0, unanswered_gaps=["论点生成失败"])

        claims: List[Claim] = []
        prefix = "BULL" if side == "bull" else "BEAR"
        for idx, raw in enumerate(data.get("claims") or [], start=1):
            if not isinstance(raw, dict):
                continue
            statement = str(raw.get("statement") or "").strip()
            if not statement:
                continue
            strength = str(raw.get("strength") or "medium").lower()
            if strength not in ("high", "medium", "low"):
                strength = "medium"
            claims.append(Claim(
                claim_id=str(raw.get("claim_id") or f"CLM-{prefix}-{idx:02d}"),
                side=side,
                statement=statement,
                evidence_ids=[str(x) for x in (raw.get("evidence_ids") or []) if x],
                reasoning=str(raw.get("reasoning") or ""),
                strength=strength,
                assumptions=[str(x) for x in (raw.get("assumptions") or []) if x],
                falsifiers=[str(x) for x in (raw.get("falsifiers") or []) if x],
                time_horizon=str(raw.get("time_horizon") or ""),
            ))

        confidence = data.get("confidence", 0.5)
        try:
            confidence = max(0.0, min(1.0, float(confidence)))
        except (TypeError, ValueError):
            confidence = 0.5
        # 单边论据过少 → 置信度封顶
        if len(claims) < 2:
            confidence = min(confidence, 0.4)

        return Thesis(
            side=side,
            core_claim=str(data.get("core_claim") or ""),
            claims=claims,
            key_assumptions=[str(x) for x in (data.get("key_assumptions") or []) if x],
            kill_criteria=[str(x) for x in (data.get("kill_criteria") or []) if x],
            confidence=confidence,
            unanswered_gaps=[str(x) for x in (data.get("unanswered_gaps") or []) if x],
        )

    # ---------- R1 攻击 ----------

    def attack(self, side: str, opponent: Thesis, round_no: int = 1) -> List[DebateTurn]:
        label = SIDE_LABEL.get(side, side)
        targets = _strongest(opponent.claims, 2)
        if not targets:
            return []
        system = (
            f"你是{label}研究员。请攻击对方最强的论点。\n"
            "硬性规则：\n"
            "1. 只能攻击给定的 target_claim_id，不能自选其他论点。\n"
            "2. attack_type 必须属于：evidence_gap / logic / caliber / timing / base_rate / priced_in。\n"
            "3. 不得引入证据台账之外的新事实；需要数据请写进 argument 的'缺什么数据'，不要编造。\n"
            "4. 不得攻击对方立场或语气，只攻击论证本身。\n"
            "只输出 JSON。"
        )
        user = (
            f"对方论点：\n{_format_claims(targets)}\n\n"
            f"证据台账：\n{self.ledger.format_for_prompt(limit_per_category=12)}\n\n"
            "输出 JSON：{\"attacks\":[{\"target_claim_id\":\"...\",\"attack_type\":\"...\","
            "\"argument\":\"...\",\"cited_evidence_ids\":[\"...\"]}]}"
        )
        data = self.llm.json(system, user, max_tokens=3500, required_keys=["attacks"])
        if not data:
            return []
        valid_ids = {c.claim_id for c in targets}
        turns: List[DebateTurn] = []
        for raw in data.get("attacks") or []:
            if not isinstance(raw, dict):
                continue
            target = str(raw.get("target_claim_id") or "")
            if target not in valid_ids:
                continue
            attack_type = str(raw.get("attack_type") or "")
            if attack_type not in ATTACK_TYPES:
                attack_type = "logic"
            turns.append(DebateTurn(
                round=round_no,
                side=side,
                action="attack",
                target_claim_id=target,
                attack_type=attack_type,
                argument=str(raw.get("argument") or "").strip(),
                cited_evidence_ids=[
                    str(x) for x in (raw.get("cited_evidence_ids") or []) if x
                ],
            ))
        return turns

    # ---------- R2 防守 / 让步 ----------

    def answer(
        self,
        side: str,
        own: Thesis,
        attacks: List[DebateTurn],
        round_no: int = 2,
    ) -> List[DebateTurn]:
        label = SIDE_LABEL.get(side, side)
        if not attacks:
            return []
        own_map = {c.claim_id: c for c in own.claims}
        target_attacks = [a for a in attacks if a.target_claim_id in own_map]
        if not target_attacks:
            return []

        system = (
            f"你是{label}研究员。请逐条回应针对你的攻击。\n"
            "每条必须三选一：\n"
            "- defend：攻击不成立，必须引用证据或补充推理\n"
            "- revise：修正表述或下调 strength，说明改了哪里\n"
            "- concede：撤回该论点，说明为什么\n"
            "若本轮零让步，必须在 no_concession_reason 中说明理由（不少于 150 字），否则视为无效回应。\n"
            "真正的对抗不等于死守，也不等于轻易投降。只输出 JSON。"
        )
        user = (
            f"你的论点：\n{_format_claims([own_map[a.target_claim_id] for a in target_attacks])}\n\n"
            f"对方攻击：\n{_format_attacks(target_attacks)}\n\n"
            f"证据台账：\n{self.ledger.format_for_prompt(limit_per_category=12)}\n\n"
            "输出 JSON：{\"responses\":[{\"target_claim_id\":\"...\",\"action\":\"defend|revise|concede\","
            "\"argument\":\"...\",\"concession\":\"撤回时写撤回了什么\"}],"
            "\"no_concession_reason\":\"本轮零让步时必填\"}"
        )
        data = self.llm.json(system, user, max_tokens=4000, required_keys=["responses"])
        if not data:
            return []

        turns: List[DebateTurn] = []
        for raw in data.get("responses") or []:
            if not isinstance(raw, dict):
                continue
            target = str(raw.get("target_claim_id") or "")
            if target not in own_map:
                continue
            action = str(raw.get("action") or "").lower()
            if action not in ("defend", "revise", "concede"):
                action = "defend"
            turns.append(DebateTurn(
                round=round_no,
                side=side,
                action=action,  # type: ignore[arg-type]
                target_claim_id=target,
                argument=str(raw.get("argument") or "").strip(),
                concession=str(raw.get("concession") or "").strip(),
            ))

        conceded = any(t.action == "concede" for t in turns)
        reason = str(data.get("no_concession_reason") or "").strip()
        if not conceded:
            turns.append(DebateTurn(
                round=round_no,
                side=side,
                action="defend",
                argument="本轮未让步",
                no_concession_reason=reason or "未说明理由",
            ))
        return turns

    # ---------- 编排 ----------

    def run(
        self,
        bull: Thesis,
        bear: Thesis,
        max_rounds: int = 2,
    ) -> Dict[str, Any]:
        """
        执行辩论。返回 {turns, conceded, stopped_reason}。

        R1 双方攻击；R2 双方回应。两轮内无新增信息则停止。
        """
        turns: List[DebateTurn] = []
        if max_rounds <= 0:
            return {"turns": turns, "conceded": False, "stopped_reason": "辩论未启用"}

        # 双方攻击并行（互不依赖，LLM 客户端与台账均支持并发）
        with cf.ThreadPoolExecutor(max_workers=2) as pool:
            bull_future = pool.submit(self.attack, "bull", bear, 1)
            bear_future = pool.submit(self.attack, "bear", bull, 1)
            bull_attacks = bull_future.result()
            bear_attacks = bear_future.result()
        turns.extend(bull_attacks)
        turns.extend(bear_attacks)
        if not bull_attacks and not bear_attacks:
            return {"turns": turns, "conceded": False, "stopped_reason": "无有效攻击"}

        if max_rounds >= 2:
            with cf.ThreadPoolExecutor(max_workers=2) as pool:
                bull_future = pool.submit(self.answer, "bull", bull, bear_attacks, 2)
                bear_future = pool.submit(self.answer, "bear", bear, bull_attacks, 2)
                turns.extend(bull_future.result())
                turns.extend(bear_future.result())

        conceded = any(t.action == "concede" for t in turns)
        return {
            "turns": turns,
            "conceded": conceded,
            "stopped_reason": "达到轮次上限",
        }


# ---------- 格式化 ----------

def _strongest(claims: List[Claim], limit: int) -> List[Claim]:
    order = {"high": 0, "medium": 1, "low": 2}
    ordered = sorted(claims, key=lambda c: order.get(c.strength, 3))
    return ordered[:limit]


def _format_claims(claims: List[Claim]) -> str:
    lines = []
    for claim in claims:
        lines.append(
            json.dumps({
                "claim_id": claim.claim_id,
                "statement": claim.statement,
                "strength": claim.strength,
                "evidence_ids": claim.evidence_ids,
                "assumptions": claim.assumptions,
                "falsifiers": claim.falsifiers,
            }, ensure_ascii=False)
        )
    return "\n".join(lines) or "（无）"


def _format_attacks(attacks: List[DebateTurn]) -> str:
    lines = []
    for attack in attacks:
        lines.append(
            json.dumps({
                "target_claim_id": attack.target_claim_id,
                "attack_type": attack.attack_type,
                "argument": attack.argument,
                "cited_evidence_ids": attack.cited_evidence_ids,
            }, ensure_ascii=False)
        )
    return "\n".join(lines) or "（无）"
