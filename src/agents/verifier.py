#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
质检（Verifier）

两级校验：
1. 机械校验（纯代码、可单测）：引用存在、数字一致、口径、时效、合规、覆盖率
2. LLM 校验：focus_questions 是否答完、论证跳跃、风险低估

设计原则：机械校验必须能独立运行，不依赖任何外部服务。
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Iterable, List, Optional

from agents.ledger import EvidenceLedger
from agents.state import (
    Claim,
    Thesis,
    VerificationIssue,
    VerificationReport,
    Verdict,
)

logger = logging.getLogger(__name__)

# 合规阻断词（确定性买卖指令 / 收益承诺 / 目标价）
COMPLIANCE_PATTERNS = (
    r"必涨", r"必跌", r"保证(收益|盈利)", r"稳赚", r"无风险(收益)?",
    r"(满仓|全仓|清仓)(买入|卖出)?", r"目标价", r"确定性收益",
    r"建议(立即)?(买入|卖出|抄底|清仓)",
)

# 负面证据关键词（用于风险低估检查）
NEGATIVE_WORDS = (
    "下滑", "下降", "亏损", "减持", "处罚", "立案", "违约", "下调",
    "暴雷", "退市", "商誉减值", "不及预期", "裁员", "诉讼", "质押", "问询",
)

_CALIBER_RE = re.compile(r"(PE\(TTM\)|PE\(动态\)|PE|PB|PS\(TTM\)|PS|股息率)", re.IGNORECASE)


def _caliber_core(caliber: str) -> str:
    """提取口径核心（去掉来源前缀/周期后缀），用于判断是否同一口径"""
    match = _CALIBER_RE.search(caliber or "")
    return match.group(1).upper() if match else ""


_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?\s*%")
_TOLERANCE = 0.005  # 0.5%


class Verifier:
    """质检器"""

    def __init__(self, ledger: EvidenceLedger, as_of: Optional[str] = None):
        self.ledger = ledger
        self.as_of = as_of or ledger.as_of

    # ---------- 机械校验 ----------

    def check_mechanical(
        self,
        bull: Optional[Thesis],
        bear: Optional[Thesis],
        verdict: Verdict,
        focus_questions: Optional[List[str]] = None,
        stale_days: int = 400,
    ) -> VerificationReport:
        issues: List[VerificationIssue] = []
        checks = 0

        theses = [t for t in (bull, bear) if t is not None]
        claims: List[Claim] = [c for t in theses for c in t.claims]

        # 1. 引用存在
        checks += 1
        for claim in claims:
            missing = self.ledger.validate(claim.evidence_ids)
            if missing:
                issues.append(VerificationIssue(
                    kind="invalid_ref",
                    detail=f"claim {claim.claim_id} 引用了不存在的证据: {', '.join(missing)}",
                    target=claim.claim_id,
                    severity="blocking",
                ))
        for eid in verdict.evidence_ids:
            if self.ledger.validate([eid]):
                issues.append(VerificationIssue(
                    kind="invalid_ref",
                    detail=f"裁决引用了不存在的证据: {eid}",
                    target="verdict",
                    severity="blocking",
                ))

        # 2. 论点必须有证据
        checks += 1
        for claim in claims:
            if not claim.evidence_ids:
                issues.append(VerificationIssue(
                    kind="missing_evidence",
                    detail=f"claim {claim.claim_id} 未引用任何证据",
                    target=claim.claim_id,
                    severity="blocking",
                ))

        # 3. 数字一致性：claim 中的百分比数字至少要能在引用证据中找到
        checks += 1
        for claim in claims:
            referenced = [self.ledger.get(eid) for eid in claim.evidence_ids]
            referenced = [e for e in referenced if e is not None]
            if not referenced:
                continue
            haystack = " ".join(
                f"{e.statement} {e.value}" for e in referenced
            )
            for number in _NUMBER_RE.findall(claim.statement):
                if not _number_in_text(number, haystack):
                    issues.append(VerificationIssue(
                        kind="number_mismatch",
                        detail=f"claim {claim.claim_id} 中的 {number.strip()} 在引用证据中找不到对应数值",
                        target=claim.claim_id,
                        severity="warning",
                    ))

        # 4. 口径冲突：同一资产、同一指标出现不同口径（PE/PB/PS/股息率各自比较）
        checks += 1
        metric_cores: Dict[tuple, set] = {}
        for item in self.ledger.all():
            if item.category != "valuation" or not item.caliber:
                continue
            core = _caliber_core(item.caliber)
            if not core:
                continue
            metric = core.split("(")[0]
            metric_cores.setdefault((item.asset_id, metric), set()).add(core)
        for (asset_id, metric), cores in metric_cores.items():
            if len(cores) > 1:
                issues.append(VerificationIssue(
                    kind="caliber_conflict",
                    detail=f"{asset_id or '未知资产'} 的 {metric} 存在不同口径: {', '.join(sorted(cores))}",
                    target="verdict",
                    severity="warning",
                ))

        # 5. 时效：核心论点只依赖过旧证据
        checks += 1
        if self.as_of:
            from utils.pit import parse_date

            ref = parse_date(self.as_of)
            for claim in claims:
                if claim.strength != "high" or not ref:
                    continue
                dates = [
                    parse_date(self.ledger.get(eid).source_time)  # type: ignore[union-attr]
                    for eid in claim.evidence_ids
                    if self.ledger.get(eid) and self.ledger.get(eid).source_time  # type: ignore[union-attr]
                ]
                dates = [d for d in dates if d is not None]
                if dates and max(dates) and (ref - max(dates)).days > stale_days:
                    issues.append(VerificationIssue(
                        kind="stale_evidence",
                        detail=f"claim {claim.claim_id} 为高强度论点，但全部证据早于 {stale_days} 天",
                        target=claim.claim_id,
                        severity="warning",
                    ))

        # 6. 合规
        checks += 1
        text_blob = " ".join(
            [verdict.summary, verdict.position_hint, verdict.confidence_calibration]
            + list(verdict.key_drivers)
            + [c.statement for c in claims]
        )
        for pattern in COMPLIANCE_PATTERNS:
            if re.search(pattern, text_blob):
                issues.append(VerificationIssue(
                    kind="compliance",
                    detail=f"命中合规敏感表述: {pattern}",
                    target="verdict",
                    severity="blocking",
                ))

        # 7. 论点质量：高强度 claim 必须有可证伪条件
        checks += 1
        for claim in claims:
            if claim.strength == "high" and not claim.falsifiers:
                issues.append(VerificationIssue(
                    kind="missing_falsifier",
                    detail=f"claim {claim.claim_id} 为高强度但未给可证伪条件",
                    target=claim.claim_id,
                    severity="blocking",
                ))

        # 8. 证据覆盖率：至少两个类别、至少 3 条证据
        checks += 1
        categories = {item.category for item in self.ledger.all()}
        if self.ledger.count() < 3 or len(categories) < 2:
            issues.append(VerificationIssue(
                kind="thin_evidence",
                detail=f"证据不足：{self.ledger.count()} 条，覆盖 {len(categories)} 类",
                target="verdict",
                severity="warning",
            ))

        # 9. 风险低估：负面证据 >= 2 但没有任何结构化风险
        checks += 1
        negative = self._count_negative()
        if negative >= 2 and not verdict.structured_risks:
            issues.append(VerificationIssue(
                kind="risk_understated",
                detail=f"台账含 {negative} 条负面证据，但裁决未列任何结构化风险",
                target="verdict",
                severity="blocking",
            ))

        # 10. focus_questions 机械可判部分：问题关键词是否在裁决中出现
        checks += 1
        if focus_questions:
            evidence_text = " ".join(item.statement for item in self.ledger.all())
            blob = (
                verdict.summary + " " + " ".join(verdict.key_drivers) + " "
                + " ".join(verdict.falsifiers_to_watch) + " " + evidence_text
            )
            for question in focus_questions:
                tokens = [t for t in _keywords(question) if len(t) >= 2]
                if tokens and not any(t in blob for t in tokens):
                    issues.append(VerificationIssue(
                        kind="question_unaddressed",
                        detail=f"研究问题可能未被回答: {question}",
                        target="verdict",
                        severity="warning",
                    ))

        # 11. 论点缺失（一方 JSON 截断时流程仍可继续，但必须显式标注）
        checks += 1
        for side, thesis in (("bull", bull), ("bear", bear)):
            if thesis is None or not thesis.claims:
                issues.append(VerificationIssue(
                    kind="thesis_missing",
                    detail=f"{side} 方没有生成有效论点，辩论与裁决的信息量下降",
                    target=side,
                    severity="warning",
                ))

        passed = not any(issue.severity == "blocking" for issue in issues)
        return VerificationReport(passed=passed, checks_run=checks, issues=issues)

    def _count_negative(self) -> int:
        count = 0
        for item in self.ledger.all():
            text = f"{item.statement} {item.value}"
            if any(word in text for word in NEGATIVE_WORDS):
                count += 1
            elif isinstance(item.value, (int, float)) and item.value < 0:
                count += 1
        return count

    # ---------- LLM 校验 ----------

    def check_llm(
        self,
        llm: Any,
        query: str,
        plan: Any,
        bull: Optional[Thesis],
        bear: Optional[Thesis],
        verdict: Verdict,
    ) -> List[VerificationIssue]:
        """LLM 视角的质检：论证跳跃、风险低估、问题未答。失败时返回空列表。"""
        system = (
            "你是投研质检员。只做检查，不重写报告。\n"
            "检查三件事：\n"
            "1. 每个高强度论点是否存在'从证据到结论'的跳跃（证据不支持结论强度）\n"
            "2. 裁决是否系统性低估台账中的负面证据\n"
            "3. 用户的研究问题是否被回答或被明确标注为无法回答\n"
            "只输出 JSON：{\"issues\":[{\"kind\":\"logic_jump|risk_understated|question_unaddressed\","
            "\"detail\":\"...\",\"target\":\"claim_id 或 verdict\",\"severity\":\"blocking|warning\"}]}\n"
            "没有问题时输出 {\"issues\":[]}。不要为了凑数而编造问题。\n"
            "判定标准：多空论据、否证信号、跟踪指标由流程自动生成，不算未回答；"
            "只有具体数据/事实类问题在证据台账和结论中完全找不到对应事实时，才报 question_unaddressed。"
        )
        claims_text = "\n".join(
            f"[{c.claim_id}|{c.strength}] {c.statement} <- {','.join(c.evidence_ids)}"
            for t in (bull, bear) if t for c in t.claims
        )
        negative_text = "\n".join(
            f"[{i.evidence_id}] {i.statement}"
            for i in self.ledger.all()
            if any(w in i.statement for w in NEGATIVE_WORDS)
        ) or "（无）"
        user = (
            f"用户问题：{query}\n"
            f"研究问题清单：{getattr(plan, 'focus_questions', [])}\n\n"
            f"证据台账：\n{self.ledger.format_for_prompt(limit_per_category=20)}\n\n"
            f"论点：\n{claims_text or '（无）'}\n\n"
            f"负面证据：\n{negative_text}\n\n"
            f"裁决：{verdict.model_dump_json(ensure_ascii=False)}"
        )
        data = llm.json(system, user, max_tokens=2048, required_keys=["issues"])
        if not data:
            return []
        issues: List[VerificationIssue] = []
        for raw in data.get("issues") or []:
            if not isinstance(raw, dict):
                continue
            detail = str(raw.get("detail") or "").strip()
            if not detail:
                continue
            severity = str(raw.get("severity") or "warning").lower()
            issues.append(VerificationIssue(
                kind=str(raw.get("kind") or "llm_check"),
                detail=detail,
                target=str(raw.get("target") or "verdict"),
                severity="blocking" if severity == "blocking" else "warning",
            ))
        return issues

    # ---------- 汇总 ----------

    def verify(
        self,
        llm: Any = None,
        query: str = "",
        plan: Any = None,
        bull: Optional[Thesis] = None,
        bear: Optional[Thesis] = None,
        verdict: Optional[Verdict] = None,
    ) -> VerificationReport:
        if verdict is None:
            return VerificationReport(passed=False, issues=[VerificationIssue(
                kind="missing_verdict", detail="缺少裁决", severity="blocking",
            )])
        report = self.check_mechanical(
            bull=bull,
            bear=bear,
            verdict=verdict,
            focus_questions=list(getattr(plan, "focus_questions", []) or []),
        )
        if llm is not None:
            try:
                report.issues.extend(self.check_llm(llm, query, plan, bull, bear, verdict))
            except Exception as exc:  # noqa: BLE001  (LLM 质检失败不应阻断主流程)
                logger.warning("LLM 质检失败（降级为机械校验）: %s", exc)
                report.issues.append(VerificationIssue(
                    kind="llm_check_failed", detail=str(exc), severity="warning",
                ))
        report.passed = not any(issue.severity == "blocking" for issue in report.issues)
        return report


def _number_in_text(number: str, haystack: str) -> bool:
    """判断数字（百分比）是否出现在文本中，容差 0.5%"""
    clean = number.replace("%", "").replace(" ", "")
    try:
        target = float(clean)
    except ValueError:
        return True
    for token in re.findall(r"-?\d+(?:\.\d+)?", haystack):
        try:
            value = float(token)
        except ValueError:
            continue
        if abs(value - target) <= max(abs(target) * _TOLERANCE, 0.05):
            return True
    return False


def _keywords(text: str) -> List[str]:
    """粗粒度关键词：连续中文/字母数字片段"""
    return re.findall(r"[\u4e00-\u9fa5A-Za-z0-9]{2,}", text)
