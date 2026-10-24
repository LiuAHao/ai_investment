#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
投研流水线（6 层）

L0 Supervisor → L1 取证（并行）→ L2 论点（并行、互不可见）
→ L3 辩论 → L4 裁决（盲判 + 终判）→ L5 质检（有界回退）
→ L6 决策落库

设计约束：
- 事实只来自 EvidenceLedger
- 每阶段有预算与超时
- 失败显式降级，不伪造结论
"""

from __future__ import annotations

import concurrent.futures
import logging
import re
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from agents import events
from agents.budget import Budget, Trace
from agents.debate import Debater
from agents.judge import Judge
from agents.ledger import EvidenceLedger
from agents.llm import BudgetExceeded, LLM
from agents.state import (
    AgentResult,
    AgentTask,
    AnalystOutput,
    Asset,
    InvestmentAnswer,
    LedgerEvidence,
    ResearchPlan,
    Thesis,
    VerificationIssue,
    VerificationReport,
    Verdict,
)
from agents.verifier import Verifier
from analysts import registry as analyst_registry
from analysts.base import parse_analyst_payload
from memory import decision_store, reflection, settlement
from utils import pit
from utils.llm_common import get_env

logger = logging.getLogger(__name__)

ANALYST_TIMEOUT_SECONDS = 180
THESIS_TIMEOUT_SECONDS = 120
MAX_ANALYSTS = 4
BENCHMARKS = {
    "cn_stock": "000300",
    "etf": "000300",
    "index": "000300",
    "us_stock": "SPX",
    "hk_stock": "HSI",
    "fund": "000300",
}


class Pipeline:
    """投研主流水线"""

    def __init__(self, task_id: str = "", model: Optional[str] = None, cache: Any = None):
        self.task_id = task_id or f"task_{uuid.uuid4().hex[:12]}"
        self.model = model
        self.cache = cache
        self._thoughts: List[str] = []

    # ==================== 主入口 ====================

    def run(
        self,
        session_id: str,
        query: str,
        risk_preference: str = "",
        context: str = "",
        as_of: Optional[str] = None,
    ) -> Dict[str, Any]:
        as_of = as_of or pit.get_as_of()
        self._is_backtest = str(session_id).startswith("backtest")
        trace = Trace()
        degraded = False
        ledger = EvidenceLedger(as_of=as_of)

        self._settle_in_background()
        self._think(f"开始研究：{query[:60]}")

        with pit.pit_mode(as_of):
            # ---------- L0 计划 ----------
            self._emit_phase_start("L0", "研究计划", ["Supervisor"])
            with trace.measure("L0") as phase:
                assets = self._resolve_assets(query, session_id)
                plan = self._supervise(query, assets, risk_preference, context)
                budget = Budget.from_plan(plan)
                phase.detail = {"analysts": [analyst_registry.analyst_label(n) for n in plan.analyst_names()], "debate": plan.debate}
            self._emit_phase_end("L0", trace.phases[-1], degraded=False)
            self._think(f"计划：{' + '.join(analyst_registry.analyst_label(n) for n in plan.analyst_names())}（{plan.reason}）")

            # ---------- L1 取证 ----------
            self._emit_phase_start("L1", "证据采集", [analyst_registry.analyst_label(n) for n in plan.analyst_names()])
            with trace.measure("L1") as phase:
                outputs = self._collect(
                    plan=plan,
                    assets=assets,
                    query=query,
                    context=context,
                    risk_preference=risk_preference,
                    ledger=ledger,
                    budget=budget,
                )
                degraded = any(o.degraded for o in outputs)
                phase.degraded = degraded
                phase.detail = {
                    "evidence": ledger.count(),
                    "categories": ledger.summary(),
                    "failed": [o.analyst for o in outputs if o.degraded],
                }
            self._emit_phase_end("L1", trace.phases[-1], degraded=degraded)

            # 无任何证据时不进入论点/裁决，避免模型凭空编造
            if ledger.count() == 0:
                self._think("未获取到任何有效证据，跳过论点与辩论，直接给出降级结论")
                return self._no_evidence_result(
                    session_id=session_id,
                    query=query,
                    assets=assets,
                    plan=plan,
                    outputs=outputs,
                    ledger=ledger,
                    trace=trace,
                    budget=budget,
                )

            # ---------- L2 论点 ----------
            llm = LLM(model=self.model, budget=budget, cache=self.cache, task_id=self.task_id)
            self._emit_phase_start("L2", "多空建论", ["BullThesis", "BearThesis"])
            with trace.measure("L2") as phase:
                bull, bear = self._build_theses(
                    llm=llm, plan=plan, assets=assets, query=query, ledger=ledger,
                )
                phase.detail = {
                    "bull_claims": len(bull.claims),
                    "bear_claims": len(bear.claims),
                }
            self._emit_phase_end("L2", trace.phases[-1], degraded=not bull.claims or not bear.claims)

            # ---------- L3 辩论 ----------
            controversy = self._controversy(ledger, bull, bear)
            turns: List[Any] = []
            rounds = 0
            debate_stopped = "未启用"
            skipped_reason = ""
            if not plan.debate:
                skipped_reason = "debate_disabled"
                debate_stopped = "未启用辩论"
            elif not (bull.claims and bear.claims):
                skipped_reason = "insufficient_theses"
                debate_stopped = "一方论点缺失，跳过辩论"
            else:
                rounds = 2 if controversy.get("score", 0) >= 0.6 else 1

            if not rounds:
                self._emit_phase_start("L3", "结构化辩论", ["Bull", "Bear"])
                events.phase_completed(
                    self.task_id, "L3", 0, degraded=False,
                    detail={
                        "skipped": True,
                        "reason": skipped_reason or "insufficient_theses",
                        "controversy": controversy,
                    },
                )
            else:
                self._emit_phase_start("L3", "结构化辩论", ["Bull", "Bear"])
                with trace.measure("L3") as phase:
                    try:
                        result = Debater(llm, ledger, self.task_id).run(bull, bear, max_rounds=rounds)
                        turns = result.get("turns") or []
                        debate_stopped = str(result.get("stopped_reason") or "")
                        for turn in turns:
                            events.debate_turn(self.task_id, turn.model_dump())
                        phase.detail = {
                            "turns": len(turns),
                            "conceded": result.get("conceded"),
                            "rounds": rounds,
                            "controversy": controversy.get("score"),
                        }
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("辩论失败，直接进入裁决: %s", exc)
                        debate_stopped = f"辩论异常: {exc}"
                        phase.degraded = True
                self._emit_phase_end("L3", trace.phases[-1], degraded=bool(trace.phases[-1]["degraded"]))

            debate_payload = {
                "enabled": plan.debate,
                "executed": bool(turns),
                "rounds": rounds,
                "stopped_reason": debate_stopped,
                "controversy": controversy,
                "turns": [t.model_dump() for t in turns],
            }

            # ---------- L4 裁决 ----------
            self._emit_phase_start("L4", "裁决", ["Judge"])
            with trace.measure("L4") as phase:
                judge = Judge(llm, ledger, self.task_id)
                blind = judge.blind(query, bull, bear, plan.focus_questions)
                verdict = judge.final(
                    query=query,
                    bull=bull,
                    bear=bear,
                    blind=blind,
                    turns=turns,
                    focus_questions=plan.focus_questions,
                    horizon=plan.horizon,
                    debate_enabled=plan.debate,
                )
                events.verdict_ready(self.task_id, verdict.model_dump())
                phase.detail = {
                    "stance": verdict.stance,
                    "conviction": verdict.conviction,
                    "blind_stance": verdict.blind_stance,
                    "turns": len(turns),
                }
            self._emit_phase_end("L4", trace.phases[-1], degraded=not verdict.summary)

            # ---------- L5 质检 ----------
            self._emit_phase_start("L5", "质检", ["Verifier"])
            with trace.measure("L5") as phase:
                report, verdict = self._verify_and_repair(
                    llm=llm,
                    ledger=ledger,
                    plan=plan,
                    query=query,
                    bull=bull,
                    bear=bear,
                    verdict=verdict,
                    budget=budget,
                    assets=assets,
                    context=context,
                    risk_preference=risk_preference,
                )
                phase.degraded = not report.passed
                phase.detail = {
                    "passed": report.passed,
                    "issues": len(report.issues),
                    "attempts": report.attempts,
                }
            degraded = degraded or not report.passed
            self._emit_phase_end("L5", trace.phases[-1], degraded=not report.passed)

            # ---------- L6 决策落库 ----------
            self._emit_phase_start("L6", "决策记录", ["DecisionStore"])
            with trace.measure("L6") as phase:
                decision_id = self._save_decision(
                    session_id=session_id,
                    query=query,
                    assets=assets,
                    plan=plan,
                    verdict=verdict,
                    bull=bull,
                    bear=bear,
                    ledger=ledger,
                    report=report,
                    degraded=degraded,
                    as_of=as_of,
                    debate=debate_payload,
                )
                phase.detail = {"decision_id": decision_id}
            self._emit_phase_end("L6", trace.phases[-1])

        # ---------- 汇总 ----------
        answer = self._to_answer(
            query=query,
            session_id=session_id,
            assets=assets,
            plan=plan,
            verdict=verdict,
            bull=bull,
            bear=bear,
            outputs=outputs,
            ledger=ledger,
            report=report,
            degraded=degraded,
        )
        events.final_answer(self.task_id, answer.model_dump())
        trace_dict = trace.to_dict()
        self._save_trace(trace_dict, budget.snapshot())

        return {
            "query": query,
            "assets": [a.model_dump() for a in assets],
            "plan": {
                "agents": [analyst_registry.analyst_label(n) for n in plan.analyst_names()],
                "reason": plan.reason,
                "intent": plan.intent,
                "horizon": plan.horizon,
                "debate": plan.debate,
                "focus_questions": plan.focus_questions,
                "required_analysts": plan.required_analysts,
                "optional_analysts": plan.optional_analysts,
            },
            "agent_results": [self._output_to_result(o) for o in outputs],
            "analyst_outputs": [o.model_dump() for o in outputs],
            "answer": answer.model_dump(),
            "verdict": verdict.model_dump(),
            "thesis": {"bull": bull.model_dump(), "bear": bear.model_dump()},
            "debate": debate_payload,
            "evidence": [e.model_dump() for e in ledger.all()],
            "verification": report.model_dump(),
            "decision_id": decision_id,
            "trace": {**trace_dict, "budget": budget.snapshot()},
            "budget": budget.snapshot(),
            "orchestrator": {
                "thoughts": self._thoughts,
                "plan": [analyst_registry.analyst_label(n) for n in plan.analyst_names()],
                "reason": plan.reason,
            },
        }

    # ==================== L0 ====================

    def _think(self, text: str) -> None:
        self._thoughts.append(text)
        events.orchestrator_thinking(self.task_id, text)

    def _resolve_assets(self, query: str, session_id: str) -> List[Asset]:
        try:
            from tools.registry import get_tool_registry

            result = get_tool_registry().execute("asset_resolve", {"query": query})
            selected = result.data.get("selected_assets", []) if result else []
            assets = [Asset(**item) for item in selected]
            if assets:
                names = ", ".join(a.name or a.symbol or "" for a in assets)
                self._think(f"资产识别：{names}")
                return assets
        except Exception as exc:  # noqa: BLE001
            logger.warning("资产解析失败: %s", exc)

        inherited = [] if getattr(self, "_is_backtest", False) else self._load_previous_assets(session_id)
        if inherited:
            names = ", ".join(a.name or a.symbol or "" for a in inherited)
            self._think(f"本轮未识别到资产，沿用上一轮：{names}")
            return inherited
        self._think("未识别到具体资产，按宏观/市场问题处理")
        return []

    @staticmethod
    def _load_previous_assets(session_id: str) -> List[Asset]:
        if not session_id:
            return []
        try:
            from agents.memory import get_session_memory

            session = get_session_memory().get_session(session_id)
            if not session or not session.turns:
                return []
            raw = (session.turns[-1].get("answer") or {}).get("assets") or []
            return [Asset(**item) for item in raw if isinstance(item, dict)]
        except Exception:
            return []

    def _supervise(
        self,
        query: str,
        assets: List[Asset],
        risk_preference: str,
        context: str,
    ) -> ResearchPlan:
        intent = _guess_intent(query, assets)
        has_assets = bool(assets)
        required = analyst_registry.rule_required(
                intent, query, has_assets,
                [a.asset_type.value for a in assets],
            )
        candidates = analyst_registry.optional_candidates(required)

        use_llm_plan = _should_use_llm_plan(intent, assets)
        llm = LLM(model=self.model, cache=self.cache, task_id=self.task_id) if use_llm_plan else None
        prompt = (
            "你是投研主管。你的唯一输出是一个 JSON 研究计划，不要输出任何解释或其他内容。\n\n"
            "JSON 结构（字段必须齐全）：\n"
            "{\"intent\":\"single_asset_research|compare|portfolio|macro\","
            "\"horizon\":\"short|medium|long\",\"optional_analysts\":[\"分析师的 key\"],"
            "\"debate\":true|false,\"focus_questions\":[\"3-5 个针对本题的具体问题\"],"
            "\"reason\":\"一句话计划理由\"}\n\n"
            f"本题：{query}\n"
            f"识别到的资产：{', '.join(a.name or a.symbol or '' for a in assets) or '无（宏观/市场问题）'}\n"
            f"规则已确定的必选分析师：{required}\n"
            f"optional_analysts 只能从这些 key 中选：{candidates}\n"
            f"用户风险偏好：{risk_preference or '未指定'}\n"
            f"上下文：{context[:600] or '无'}\n\n"
            "分析师 key 说明：market=行情/技术/估值，news=事件/公告/舆情，"
            "fundamental=财务/同业，macro=宏观/政策/利率。\n"
            "focus_questions 必须针对本题且可验证，例如「毛利率下滑是结构性还是季节性」，"
            "禁止写「分析一下这只股票」这类空问题。"
        )
        data: Dict[str, Any] = {}
        if llm is not None:
            data = llm.json(
                prompt,
                "请输出上述 JSON 研究计划。",
                max_tokens=1400,
                required_keys=["intent"],
                retries=0,
            ) or {}
            if not data:
                self._think("LLM 计划生成失败，使用规则保底计划")
        else:
            self._think("单票/简单问题：使用规则计划（不调用 LLM）")

        llm_intent = str(data.get("intent") or "").strip()
        if llm_intent in ("single_asset_research", "compare", "portfolio", "macro"):
            intent = llm_intent
            required = analyst_registry.rule_required(
                intent, query, has_assets,
                [a.asset_type.value for a in assets],
            )

        optional: List[str] = []
        for key in data.get("optional_analysts") or []:
            if key in candidates and key not in required and key not in optional:
                optional.append(key)

        horizon = str(data.get("horizon") or "medium")
        if horizon not in ("short", "medium", "long"):
            horizon = "medium"

        llm_questions = [str(q).strip() for q in (data.get("focus_questions") or []) if str(q).strip()]
        # 规则问题始终保底在前，LLM 问题最多补 2 条（防止模型带偏）
        focus_questions = _merge_questions(_default_questions(query, assets, intent), llm_questions)

        # 辩论是必选环节：除非双方论点都生成失败，否则至少 1 轮
        debate = True

        plan = ResearchPlan(
            intent=intent,
            assets=assets,
            horizon=horizon,
            required_analysts=required,
            optional_analysts=optional,
            debate=debate,
            focus_questions=focus_questions[:5],
            llm_calls=32,
            tool_calls=36,
            reason=str(data.get("reason") or "规则保底 + LLM 加派"),
        )
        labels = [analyst_registry.analyst_label(name) for name in plan.analyst_names()]
        plan_payload = plan.model_dump()
        plan_payload["agents"] = labels
        events.plan_ready(self.task_id, plan_payload)
        events.orchestrator_decided(self.task_id, labels, plan.reason)
        return plan

    # ==================== L1 ====================

    def _collect(
        self,
        plan: ResearchPlan,
        assets: List[Asset],
        query: str,
        context: str,
        risk_preference: str,
        ledger: EvidenceLedger,
        budget: Budget,
    ) -> List[AnalystOutput]:
        names = plan.analyst_names()[:MAX_ANALYSTS]
        agents = {}
        tasks = {}
        for key in names:
            try:
                agents[key] = analyst_registry.build_analyst(
                    key,
                    task_id=self.task_id,
                    model=self.model,
                    ledger=ledger,
                    budget=budget,
                    as_of=ledger.as_of,
                )
                tasks[key] = AgentTask(
                    agent_name=analyst_registry.analyst_label(key),
                    goal=query,
                    assets=assets,
                    context=context,
                    risk_preference=risk_preference,
                    focus_questions=plan.focus_questions,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("构建分析师失败 %s: %s", key, exc)

        outputs: Dict[str, AnalystOutput] = {}
        pool = concurrent.futures.ThreadPoolExecutor(max_workers=MAX_ANALYSTS)
        futures = {pool.submit(agents[key].run, tasks[key]): key for key in agents}
        try:
            for future in concurrent.futures.as_completed(futures, timeout=ANALYST_TIMEOUT_SECONDS):
                key = futures[future]
                try:
                    result = future.result()
                except Exception as exc:  # noqa: BLE001
                    outputs[key] = AnalystOutput(
                        analyst=analyst_registry.analyst_label(key),
                        degraded=True,
                        error=str(exc),
                    )
                    continue
                outputs[key] = self._ingest(key, result, assets, ledger)
        except concurrent.futures.TimeoutError:
            logger.warning("分析师阶段超时（>%ss），使用已完成部分", ANALYST_TIMEOUT_SECONDS)
            for future, key in futures.items():
                if key in outputs:
                    continue
                if future.done():
                    try:
                        outputs[key] = self._ingest(key, future.result(), assets, ledger)
                    except Exception as exc:  # noqa: BLE001
                        outputs[key] = AnalystOutput(
                            analyst=analyst_registry.analyst_label(key),
                            degraded=True, error=str(exc),
                        )
                else:
                    outputs[key] = AnalystOutput(
                        analyst=analyst_registry.analyst_label(key),
                        degraded=True, error=f"执行超时（>{ANALYST_TIMEOUT_SECONDS}s）",
                    )
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

        ordered = [outputs[key] for key in names if key in outputs]
        return ordered

    def _ingest(
        self,
        key: str,
        result: AgentResult,
        assets: List[Asset],
        ledger: EvidenceLedger,
    ) -> AnalystOutput:
        spec = analyst_registry.ANALYST_SPECS[key]
        raw, gaps, coverage = parse_analyst_payload(
            conclusion=result.conclusion or "",
            analyst=spec.label,
            default_category=(spec.evidence_categories[0] if spec.evidence_categories else "market"),
            allowed_tools=spec.tool_names,
        )
        # 台账的唯一来源是工具返回：模型提炼只在摘要里展示，避免复述造成重复。
        _ = raw

        return AnalystOutput(
            analyst=spec.label,
            evidence=[ledger.get(eid) for eid in result.evidence_refs if ledger.get(eid)],  # type: ignore[list-item]
            gaps=gaps,
            coverage=coverage,
            conclusion=result.conclusion or "",
            degraded=result.degraded or bool(result.error),
            error=result.error or "",
            tool_calls=result.tool_calls,
            thinking_log=result.thinking_log,
        )

    # ==================== L2 ====================

    @staticmethod
    def _controversy(
        ledger: EvidenceLedger,
        bull: Any = None,
        bear: Any = None,
    ) -> Dict[str, Any]:
        """多空争议度：证据平衡 + 论点分歧 + 背离信号。"""
        from agents.verifier import NEGATIVE_WORDS

        positive_words = (
            "增长", "回升", "改善", "超预期", "净流入", "上调", "复苏",
            "扩张", "增持", "盈利", "创新高", "转正",
        )
        pos = neg = 0
        price_ret = None
        main_flow = None
        valuation_pct = None
        growth = None
        for item in ledger.all():
            text = f"{item.statement} {item.value}"
            value = item.value if isinstance(item.value, (int, float)) else None
            if any(word in text for word in NEGATIVE_WORDS) or (value is not None and value < 0):
                neg += 1
            elif any(word in text for word in positive_words):
                pos += 1
            if item.category == "market" and "区间" in (item.statement or "") and value is not None:
                price_ret = value
            if item.category == "flow" and "主力" in (item.statement or "") and value is not None:
                main_flow = value
            if item.category == "valuation" and "分位" in (item.statement or ""):
                match = re.search(r"分位\s*(\d+(?:\.\d+)?)%", item.statement)
                if match:
                    valuation_pct = float(match.group(1))
            if item.category == "fundamental" and "同比" in (item.statement or "") and value is not None:
                growth = value

        total = pos + neg
        balance = (1 - abs(pos - neg) / total) if total else 0.5

        n_bull = len(getattr(bull, "claims", None) or [])
        n_bear = len(getattr(bear, "claims", None) or [])
        core_bull = str(getattr(bull, "core_claim", "") or "")
        core_bear = str(getattr(bear, "core_claim", "") or "")

        def _bigrams(text: str):
            cleaned = re.sub(r"\s+", "", text or "")
            return {cleaned[index:index + 2] for index in range(len(cleaned) - 1)}

        ga, gb = _bigrams(core_bull), _bigrams(core_bear)
        core_diff = (1 - len(ga & gb) / max(1, len(ga | gb))) if ga and gb else 0.0

        bull_evidence = {
            eid for claim in (getattr(bull, "claims", None) or [])
            for eid in (getattr(claim, "evidence_ids", None) or [])
        }
        bear_evidence = {
            eid for claim in (getattr(bear, "claims", None) or [])
            for eid in (getattr(claim, "evidence_ids", None) or [])
        }
        evidence_overlap = (
            len(bull_evidence & bear_evidence) / max(1, len(bull_evidence | bear_evidence))
            if bull_evidence and bear_evidence else 1.0
        )

        thesis_component = 0.0
        if n_bull >= 3 and n_bear >= 3:
            thesis_component += 0.2
        if core_diff >= 0.35:
            thesis_component += 0.15
        if evidence_overlap < 0.5:
            thesis_component += 0.05

        divergence: List[str] = []
        if price_ret is not None and main_flow is not None and price_ret * main_flow < 0:
            divergence.append("价格与主力资金背离")
        if valuation_pct is not None and growth is not None:
            if valuation_pct < 30 and growth < 0:
                divergence.append("估值低分位但盈利负增长")
            elif valuation_pct > 70 and growth > 20:
                divergence.append("估值高分位但盈利高增长")

        score = min(1.0, balance * 0.4 + thesis_component + min(len(divergence), 2) * 0.1)
        return {
            "score": round(score, 3),
            "balance": round(balance, 3),
            "positive": pos,
            "negative": neg,
            "claim_counts": {"bull": n_bull, "bear": n_bear},
            "core_diff": round(core_diff, 3),
            "evidence_overlap": round(evidence_overlap, 3),
            "divergence": divergence,
        }

    def _build_theses(
        self,
        llm: LLM,
        plan: ResearchPlan,
        assets: List[Asset],
        query: str,
        ledger: EvidenceLedger,
    ) -> Tuple[Thesis, Thesis]:
        debater = Debater(llm, ledger, self.task_id)
        reflections = ""
        try:
            if not getattr(self, "_is_backtest", False):
                reflections = reflection.get_reflections(assets)
        except Exception as exc:  # noqa: BLE001
            logger.warning("读取历史反思失败: %s", exc)

        def build(side: str) -> Thesis:
            try:
                events.thesis_started(self.task_id, side)
                thesis = debater.build_thesis(
                    side=side,
                    query=query,
                    assets=assets,
                    horizon=plan.horizon,
                    focus_questions=plan.focus_questions,
                    reflections=reflections,
                )
                events.thesis_submitted(
                    self.task_id, side, len(thesis.claims),
                    thesis.confidence, thesis.core_claim,
                    claims=[
                        {
                            "claim_id": claim.claim_id,
                            "statement": claim.statement,
                            "strength": claim.strength,
                        }
                        for claim in thesis.claims[:3]
                    ],
                )
                return thesis
            except Exception as exc:  # noqa: BLE001
                logger.warning("%s 论点构建失败: %s", side, exc)
                return Thesis(side=side, confidence=0.0, unanswered_gaps=[str(exc)])

        pool = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        futures = {pool.submit(build, side): side for side in ("bull", "bear")}
        results: Dict[str, Thesis] = {}
        try:
            for future in concurrent.futures.as_completed(futures, timeout=THESIS_TIMEOUT_SECONDS):
                side = futures[future]
                try:
                    results[side] = future.result()
                except Exception as exc:  # noqa: BLE001
                    results[side] = Thesis(side=side, confidence=0.0, unanswered_gaps=[str(exc)])
        except concurrent.futures.TimeoutError:
            for side in ("bull", "bear"):
                results.setdefault(side, Thesis(side=side, confidence=0.0, unanswered_gaps=["建论超时"]))
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
        return results["bull"], results["bear"]

    # ==================== L5 ====================

    def _verify_and_repair(
        self,
        llm: LLM,
        ledger: EvidenceLedger,
        plan: ResearchPlan,
        query: str,
        bull: Thesis,
        bear: Thesis,
        verdict: Verdict,
        budget: Budget,
        assets: List[Asset],
        context: str,
        risk_preference: str,
    ) -> Tuple[Any, Verdict]:
        verifier = Verifier(ledger, as_of=ledger.as_of)
        report = verifier.verify(
            llm=llm, query=query, plan=plan, bull=bull, bear=bear, verdict=verdict,
        )
        if report.passed:
            return report, verdict

        events.verification_failed(
            self.task_id, [i.model_dump() for i in report.issues], "verdict",
        )

        # 证据过薄：定向补派 1 个分析师
        thin = any(i.kind in ("thin_evidence", "missing_evidence") for i in report.issues)
        if thin and budget.spend_repair():
            self._supplement_evidence(plan, assets, query, context, risk_preference, ledger, budget)
            report = verifier.verify(
                llm=llm, query=query, plan=plan, bull=bull, bear=bear, verdict=verdict,
            )
            report.repaired = True

        # 仍不通过：带问题重写裁决
        if not report.passed and budget.spend_repair():
            issues = [f"[{i.kind}] {i.detail}" for i in report.issues]
            try:
                blind = {
                    "stance": verdict.blind_stance or verdict.stance,
                    "conviction": verdict.blind_conviction,
                }
                verdict = Judge(llm, ledger, self.task_id).final(
                    query=query,
                    bull=bull,
                    bear=bear,
                    blind=blind,
                    turns=[],
                    focus_questions=plan.focus_questions,
                    horizon=plan.horizon,
                    debate_enabled=plan.debate,
                    issues=issues,
                )
                report = verifier.verify(
                    llm=llm, query=query, plan=plan, bull=bull, bear=bear, verdict=verdict,
                )
                report.repaired = True
                report.attempts += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("裁决重写失败: %s", exc)

        return report, verdict

    def _supplement_evidence(
        self,
        plan: ResearchPlan,
        assets: List[Asset],
        query: str,
        context: str,
        risk_preference: str,
        ledger: EvidenceLedger,
        budget: Budget,
    ) -> None:
        """找证据最少的分分析师补跑一次（最多 1 个）"""
        counts = ledger.summary()
        candidates = [
            key for key in plan.analyst_names()
            if not any(
                category in counts
                for category in analyst_registry.evidence_categories_for(key)
            )
        ]
        if not candidates:
            return
        key = candidates[0]
        try:
            agent = analyst_registry.build_analyst(
                key, task_id=self.task_id, model=self.model,
                ledger=ledger, budget=budget, as_of=ledger.as_of,
            )
            agent.max_iterations = 2
            task = AgentTask(
                agent_name=analyst_registry.analyst_label(key),
                goal=query,
                assets=assets,
                context=context + "\n【补充取证】上一轮缺少该类证据，请优先补齐。",
                risk_preference=risk_preference,
                focus_questions=plan.focus_questions,
            )
            result = agent.run(task)
            self._ingest(key, result, assets, ledger)
            self._think(f"定向补派 {analyst_registry.analyst_label(key)} 完成")
        except Exception as exc:  # noqa: BLE001
            logger.warning("补派分析师失败 %s: %s", key, exc)

    # ==================== L6 ====================

    def _save_decision(
        self,
        session_id: str,
        query: str,
        assets: List[Asset],
        plan: ResearchPlan,
        verdict: Verdict,
        bull: Thesis,
        bear: Thesis,
        ledger: EvidenceLedger,
        report: Any,
        degraded: bool,
        as_of: Optional[str],
        debate: Optional[Dict[str, Any]] = None,
    ) -> str:
        decision_id = f"dec_{uuid.uuid4().hex[:12]}"
        asset_ids = [a.asset_id or a.symbol or "" for a in assets if a]
        symbol = ""
        for asset in assets:
            if asset.symbol:
                symbol = asset.symbol
                break
        price = _price_snapshot(ledger)
        record = {
            "decision_id": decision_id,
            "session_id": session_id,
            "query": query,
            "asset_ids": asset_ids,
            "as_of": as_of or datetime.now().strftime("%Y-%m-%d"),
            "horizon": plan.horizon,
            "stance": verdict.stance,
            "conviction": verdict.conviction,
            "evidence_count": ledger.count(),
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "payload": {
                "verdict": verdict.model_dump(),
                "bull": bull.model_dump(),
                "bear": bear.model_dump(),
                "plan": plan.model_dump(),
                "debate": debate or {},
                "degraded": degraded,
                "verification": report.model_dump(),
                "price_snapshot": {"symbol": symbol, "price": price},
                "benchmark": _benchmark_for(assets),
                "evidence_ids": ledger.ids(),
                "evidence": [item.model_dump() for item in ledger.all()],
            },
        }
        try:
            decision_store.save_decision(record)
            events.decision_recorded(
                self.task_id, decision_id,
                record["as_of"], plan.horizon,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("决策落库失败: %s", exc)
        return decision_id

    def _no_evidence_result(
        self,
        session_id: str,
        query: str,
        assets: List[Asset],
        plan: ResearchPlan,
        outputs: List[AnalystOutput],
        ledger: EvidenceLedger,
        trace: Trace,
        budget: Budget,
    ) -> Dict[str, Any]:
        """证据为空时的降级结果：不编造方向，直接落一条低置信决策"""
        bull = Thesis(side="bull")
        bear = Thesis(side="bear")
        verdict = Verdict(
            stance="neutral",
            conviction=0.1,
            summary=(
                "本次未获取到任何有效证据，不产出方向判断。"
                "请检查数据源配置（如 TUSHARE_TOKEN）或更换研究标的。"
            ),
            revision_reason="证据台账为空，未启用论点与辩论",
            confidence_calibration="无证据支撑，任何方向判断都不可信",
            time_frame=plan.horizon,
        )
        issues = [VerificationIssue(
            kind="no_evidence", detail="证据台账为空", target="verdict", severity="blocking",
        )]
        events.verification_failed(self.task_id, [i.model_dump() for i in issues], "analysts")
        report = VerificationReport(passed=False, issues=issues, attempts=0)

        self._emit_phase_start("L6", "决策记录", ["DecisionStore"])
        with trace.measure("L6") as phase:
            decision_id = self._save_decision(
                session_id=session_id,
                query=query,
                assets=assets,
                plan=plan,
                verdict=verdict,
                bull=bull,
                bear=bear,
                ledger=ledger,
                report=report,
                degraded=True,
                as_of=ledger.as_of,
            )
            phase.detail = {"decision_id": decision_id}
        self._emit_phase_end("L6", trace.phases[-1], degraded=True)

        answer = self._to_answer(
            query=query,
            session_id=session_id,
            assets=assets,
            plan=plan,
            verdict=verdict,
            bull=bull,
            bear=bear,
            outputs=outputs,
            ledger=ledger,
            report=report,
            degraded=True,
        )
        events.final_answer(self.task_id, answer.model_dump())
        trace_dict = trace.to_dict()
        self._save_trace(trace_dict, budget.snapshot())

        return {
            "query": query,
            "assets": [a.model_dump() for a in assets],
            "plan": {
                "agents": [analyst_registry.analyst_label(n) for n in plan.analyst_names()],
                "reason": plan.reason,
                "intent": plan.intent,
                "horizon": plan.horizon,
                "debate": False,
                "focus_questions": plan.focus_questions,
                "required_analysts": plan.required_analysts,
                "optional_analysts": plan.optional_analysts,
            },
            "agent_results": [self._output_to_result(o) for o in outputs],
            "analyst_outputs": [o.model_dump() for o in outputs],
            "answer": answer.model_dump(),
            "verdict": verdict.model_dump(),
            "thesis": {"bull": bull.model_dump(), "bear": bear.model_dump()},
            "debate": {"enabled": plan.debate, "executed": False, "stopped_reason": "无证据，未进入辩论", "turns": []},
            "evidence": [],
            "verification": report.model_dump(),
            "decision_id": decision_id,
            "trace": {**trace_dict, "budget": budget.snapshot()},
            "budget": budget.snapshot(),
            "orchestrator": {
                "thoughts": self._thoughts,
                "plan": [analyst_registry.analyst_label(n) for n in plan.analyst_names()],
                "reason": plan.reason,
            },
        }

    def _save_trace(self, trace: Dict[str, Any], budget: Dict[str, int]) -> None:
        try:
            decision_store.save_trace(self.task_id, {**trace, "budget": budget})
        except Exception as exc:  # noqa: BLE001
            logger.warning("trace 落库失败: %s", exc)

    def _settle_in_background(self) -> None:
        """任务启动时后台结算到期记录（失败不影响主流程）"""
        if get_env("SETTLE_ON_START", "1") != "1":
            return

        def _worker() -> None:
            try:
                settlement.settle_pending()
            except Exception as exc:  # noqa: BLE001
                logger.warning("到期结算失败: %s", exc)

        threading.Thread(target=_worker, name="settlement", daemon=True).start()

    # ==================== 汇总 ====================

    def _to_answer(
        self,
        query: str,
        session_id: str,
        assets: List[Asset],
        plan: ResearchPlan,
        verdict: Verdict,
        bull: Thesis,
        bear: Thesis,
        outputs: List[AnalystOutput],
        ledger: EvidenceLedger,
        report: Any,
        degraded: bool,
    ) -> InvestmentAnswer:
        confidence = verdict.conviction
        if degraded or not report.passed:
            confidence = min(confidence, 0.4)
        if ledger.count() < 3:
            confidence = min(confidence, 0.5)

        gaps = [g.get("question", "") for o in outputs for g in o.gaps if g.get("question")]
        gaps.extend(
            d.topic for d in verdict.disagreement_map if d.resolvable == "needs_data"
        )
        risks = [r.get("desc", "") for r in verdict.structured_risks if r.get("desc")]

        resolved = [
            d.resolution for d in verdict.disagreement_map
            if d.resolvable == "yes" and d.resolution
        ]
        reasoning_parts = [
            f"多方核心论点：{bull.core_claim}" if bull.core_claim else "",
            f"空方核心论点：{bear.core_claim}" if bear.core_claim else "",
            f"裁决修订：{verdict.revision_reason}" if verdict.revision_reason else "",
            f"已解决分歧：{'；'.join(resolved)}" if resolved else "",
            f"置信度校准：{verdict.confidence_calibration}" if verdict.confidence_calibration else "",
        ]
        reasoning = "\n".join(p for p in reasoning_parts if p)

        return InvestmentAnswer(
            session_id=session_id,
            query=query,
            assets=assets,
            summary=verdict.summary or "（未生成结论）",
            key_points=list(verdict.key_drivers),
            evidence_refs=list(verdict.evidence_ids),
            risks=risks,
            structured_risks=list(verdict.structured_risks),
            confidence=round(confidence, 2),
            reasoning=reasoning,
            bull_cases=[
                {"point": c.statement, "strength": c.strength, "source": ",".join(c.evidence_ids)}
                for c in bull.claims
            ],
            bear_cases=[
                {"point": c.statement, "strength": c.strength, "source": ",".join(c.evidence_ids)}
                for c in bear.claims
            ],
            information_gaps=list(dict.fromkeys(gaps))[:8],
            time_frame=_localize_horizon(verdict.time_frame or plan.horizon),
        )

    @staticmethod
    def _output_to_result(output: AnalystOutput) -> Dict[str, Any]:
        return AgentResult(
            agent_name=output.analyst,
            conclusion=_readable_conclusion(output.conclusion, output),
            evidence_refs=[e.evidence_id for e in output.evidence],
            tool_calls=output.tool_calls,
            thinking_log=output.thinking_log,
            error=output.error or None,
            degraded=output.degraded,
        ).model_dump()

    # ==================== 事件 ====================

    def _emit_phase_start(self, phase: str, label: str, agents: List[str]) -> None:
        try:
            from obs import set_stage

            set_stage(phase)
        except Exception:
            pass
        events.phase_started(self.task_id, phase, label, agents)

    def _emit_phase_end(self, phase: str, entry: Dict[str, Any], degraded: bool = False) -> None:
        events.phase_completed(
            self.task_id, phase,
            int(entry.get("duration_ms", 0)),
            degraded=degraded or bool(entry.get("degraded")),
            detail=entry.get("detail") or {},
        )


# ==================== 辅助函数 ====================

_SECTOR_WORDS = (
    "板块", "行业", "赛道", "主题", "概念", "产业链", "半导体", "芯片",
    "新能源", "人工智能", "AI", "科技", "消费", "医药", "军工", "券商",
    "光伏", "风电", "机器人", "算力", "云计算", "数字经济",
)


def _guess_intent(query: str, assets: List[Asset]) -> str:
    if any(w in query for w in ("对比", "比较", "哪个好", " vs ", "VS", "还是")):
        return "compare"
    if assets:
        return "single_asset_research"
    lowered = query.lower()
    if any(word.lower() in lowered for word in _SECTOR_WORDS):
        return "sector"
    return "macro"


def _default_questions(query: str, assets: List[Asset], intent: str = "") -> List[str]:
    names = "、".join(a.name or a.symbol or "" for a in assets if a) or "当前市场"
    if intent == "sector":
        return [
            "该板块近 20/60 个交易日的相对强弱与资金流向如何",
            "板块估值分位与盈利增速是否匹配",
            "最近 3-6 个月有哪些政策、产业或事件催化",
            "多空双方各自最强的论据是什么，哪一方可被证伪",
            "未来 1-3 个月最需要跟踪的否证信号是什么",
        ]
    if len(assets) == 1:
        return [
            f"{names}当前价格与估值处于什么位置（PE/PB 及历史或同业分位）",
            f"{names}最近 2-4 个季度营收与利润的增速趋势如何",
            f"{names}最近 3-6 个月有哪些公告、政策或事件可能影响定价",
            f"{names}的多空双方各自最强的论据是什么，哪一方可被证伪",
            f"{names}未来 1-3 个月最需要跟踪的否证信号是什么",
        ]
    if len(assets) > 1:
        return [
            f"{names}的估值、增速与盈利质量差异在哪里",
            f"过去 20/60 个交易日 {names} 的相对强弱如何",
            f"{names}各自最关键的风险与催化分别是什么",
        ]
    return [
        "当前主要指数的趋势、成交额与波动率处于什么状态",
        "最近 1-3 个月的宏观数据（PMI/CPI/利率）指向什么方向",
        "近期有哪些政策或事件可能改变市场定价",
        "市场当前最一致的预期是什么，最可能被证伪的点在哪",
    ]


def _merge_questions(defaults: List[str], extra: List[str]) -> List[str]:
    """规则问题在前，LLM 问题最多补 2 条，去重后截断到 5 条"""
    merged = list(defaults)
    for question in extra:
        if question and question not in merged and len(merged) < len(defaults) + 2:
            merged.append(question)
    return merged[:5]


def _should_use_llm_plan(intent: str, assets: List[Asset]) -> bool:
    """
    计划阶段是否调用 LLM。

    默认 auto：单票走规则（快且稳定），多资产/宏观/对比才用 LLM。
    SUPERVISOR_LLM=1 强制开启，=0 强制关闭。
    """
    mode = (get_env("SUPERVISOR_LLM", "auto") or "auto").strip().lower()
    if mode in ("0", "off", "false", "no"):
        return False
    if mode in ("1", "on", "true", "yes"):
        return True
    return intent == "compare" and len(assets) > 1


def _readable_conclusion(raw: str, output: AnalystOutput) -> str:
    """
    把分析师输出转成前端可读摘要。

    三层降级：
    1. JSON 可解析 → 证据条数 + highlights
    2. JSON 截断 → 正则提取 conclusion/summary 字段
    3. 仍失败 → "采集 N 条证据，M 个问题未覆盖"
    绝不把原始 JSON 直接返回。
    """
    from agents.llm import extract_json_object

    text = (raw or "").strip()
    count = len(output.evidence)
    gaps = len(output.gaps)
    head = f"采集 {count} 条证据" if count else "完成取证"
    if gaps:
        head += f"，{gaps} 个问题未覆盖"

    data = extract_json_object(text)
    if data:
        items = data.get("highlights")
        if not isinstance(items, list):
            items = data.get("evidence") if isinstance(data.get("evidence"), list) else []
        lines = [head]
        # 统一展示：优先结构化短证据，不展示模型的长段结论
        for item in items[:3]:
            if isinstance(item, dict):
                statement = str(item.get("statement") or "").strip()
                if statement:
                    lines.append(f"- {statement[:100]}")
        if len(lines) == 1:
            summary_field = str(data.get("conclusion") or data.get("summary") or "").strip()
            if summary_field:
                lines.append(_strip_chatter(summary_field)[:160])
        return "\n".join(lines)

    # 截断 JSON：尽力提取结论字段
    if text.startswith("{"):
        extracted = _extract_json_string_field(text, ("conclusion", "summary", "answer"))
        if extracted:
            return f"{head}\n{_strip_chatter(extracted)[:160]}"
        return head

    # 纯文本：过滤对话式内容后截断
    cleaned = _strip_chatter(text)
    return f"{head}\n{cleaned[:160]}" if cleaned else head


def _extract_json_string_field(text: str, keys: tuple) -> str:
    """从未闭合/截断的 JSON 文本中提取字符串字段（容忍缺失结束引号）"""
    import json
    import re

    for key in keys:
        pattern = re.compile(r'"' + key + r'"\s*:\s*"((?:[^"\\]|\\.){10,})"')
        match = pattern.search(text)
        if match:
            try:
                return json.loads(f'"{match.group(1)}"')
            except json.JSONDecodeError:
                return match.group(1)
        # 截断在字符串内部：没有结束引号
        pattern = re.compile(r'"' + key + r'"\s*:\s*"([^"]{10,})')
        match = pattern.search(text)
        if match:
            return match.group(1)
    return ""


def _strip_chatter(text: str) -> str:
    """去掉对话式/反问式句子，避免污染摘要"""
    lines = []
    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r"^(需要我|是否要我|是否需要我|如需|要不要|我可以|我可以进一步|要不要我)", stripped):
            continue
        lines.append(stripped)
    return "\n".join(lines).strip()


def _localize_horizon(value: str) -> str:
    """把 short/medium/long 映射为中文时间框架；兼容“medium（约1-3个月）”"""
    mapping = {"short": "短期 1-4 周", "medium": "中期 1-6 个月", "long": "长期 6 个月以上"}
    short = {"short": "短期", "medium": "中期", "long": "长期"}
    text = str(value or "").strip()
    if not text:
        return mapping["medium"]
    match = re.match(r"^(short|medium|long)\b\s*[（(]?([^）)]*)[）)]?$", text, re.IGNORECASE)
    if match:
        key = match.group(1).lower()
        extra = (match.group(2) or "").strip()
        if extra:
            return f"{short[key]}（{extra}）"
        return mapping[key]
    return text


def _asset_id_for(statement: str, assets: List[Asset]) -> str:
    for asset in assets:
        for token in (asset.symbol, asset.name):
            if token and token in statement:
                return asset.asset_id or str(token)
    if len(assets) == 1:
        return assets[0].asset_id or str(assets[0].symbol or "")
    return ""


def _benchmark_for(assets: List[Asset]) -> str:
    if not assets:
        return "000300"
    return BENCHMARKS.get(assets[0].asset_type.value, "000300")


def _price_snapshot(ledger: EvidenceLedger) -> Optional[float]:
    for item in ledger.all():
        if item.category == "market" and isinstance(item.value, (int, float)):
            return float(item.value)
    return None
