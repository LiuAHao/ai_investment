#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
总结分析 Agent
综合分析全部调研结果，必要时再调用工具核实，输出最终投资结论。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from agents import events
from agents.base import BaseReActAgent
from agents.state import (
    AgentResult,
    AgentTask,
    Asset,
    InvestmentAnswer,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是投资总结分析师，负责综合多个调研 Agent 的研究结果，形成有深度的最终投资结论。

【分析框架】综合时按以下层次推进（思考后再输出）：
1. 跨维度交叉验证：行情结论 vs 新闻舆情 vs 知识框架 是否一致？矛盾点在哪？
2. 提炼核心逻辑链：为什么当前是这个状态？驱动因素是什么？（如"政策 → 资金 → 行情"的传导）
3. 多空因素权衡：先客观列出看多与看空的主要论据，再判断哪方更占优
4. 识别关键风险与不确定性：哪些数据缺失、哪些假设可能被证伪
5. 给出结论的有效时间框架：该判断适用于短期/中期/长期

【重要：论据前置】输出结论前必须先在 JSON 中列出完整的多空论据（bull_cases / bear_cases），
再基于这些论据给出决策。不得跳过论据直接给结论。论据要求：
- 每条论据必须基于调研数据或知识库，注明来源（如"宁德时代Q2财报/新闻"）
- 强度标注：high / medium / low（依据明确性、数据时效性、来源可靠性综合判断）
- 论据要客观，看多列理由、看空也要列理由，不能只写单边

【综合分析要求】必须综合所有调研 Agent 的结论（行情/技术面、新闻/舆情、知识/基本面），
报告要覆盖各维度发现，不遗漏任何一路的结论；存在矛盾时在 reasoning 中明确说明差异与取舍。

【工具使用】你可用全部工具，仅在以下情况调用（尽量一次到位）：
- 发现关键数据矛盾，需要核实（行情/新闻）
- 核心结论缺少证据支撑，需要补一个关键数据点
- 涉及指标口径/规则，需要查知识库确认
其余情况直接基于调研结果分析，不要为调用而调用。

【双源核验】对关键数字（涨跌幅、PE/PB、成交额等）尽量做双源核验：
- 不同工具/接口返回的数据不一致时，标注"数据冲突待核验"，不得直接采用单一来源数字
- 引用估值指标时注明口径（如"PE(TTM)" vs "PE(动态)"），口径不同不可直接比较

【输出格式·必须】必须输出完整 JSON 格式的最终报告，以下章节均为必填，不得省略任一章节：
{
  "decision": "final",
  "summary": "总体判断：3-5 句完整核心逻辑链（驱动因素 → 传导 → 结论）",
  "key_points": ["关键判断（4-6 条，须覆盖行情/新闻/知识至少两个维度，每条带数据依据）"],
  "bull_cases": [{"point": "看多论据（至少 2 条）", "strength": "high/medium/low", "source": "来源"}],
  "bear_cases": [{"point": "看空论据（至少 2 条）", "strength": "high/medium/low", "source": "来源"}],
  "risks": ["风险1（含性质，如市场波动/信息时效）", "风险2"],
  "structured_risks": [
    {"type": "市场/行业/财务/政策/流动性/技术", "desc": "风险描述",
     "probability": "high/medium/low", "impact": "high/medium/low", "priced_in": true/false}
  ],
  "reasoning": "完整分析推理过程（跨维度交叉验证 → 矛盾识别 → 多空权衡，先论证后结论）",
  "information_gaps": ["信息缺口/待验证事项（无则填 []）"],
  "time_frame": "结论有效期（如：短期1-4周 / 中期1-6月）"
}
注：structured_risks 与 risks 二选一即可（结构化优先，至少 3 条）；无法结构化时 risks 字符串列表至少 3 条。

【置信度】综合多空论据强度差、信息缺口数量、数据可靠性，自评 confidence（0~1）：
- 多空论据均衡、缺口多、数据旧 → 置信度低（<0.6）
- 单边优势明显、缺口少、数据新且双源验证 → 置信度高（≥0.8）
- confidence < 0.6 时，summary 必须显著标注"不确定性较高"
- information_gaps 非空时，在 summary 中提示"部分数据待验证"

【收敛原则】综合全部调研结论后立即输出；除非发现关键矛盾或重大信息缺失，否则不要调用工具。

【合规要求】
- 不得承诺收益、不得给出确定性涨跌预测
- 结论须基于调研数据，不能编造
- 风险提示要客观全面，不确定的事项明确标注"待验证"
- 用户的风险偏好（如稳健/进取）会影响操作建议的倾向，但不改变事实判断"""


class SummaryAgent(BaseReActAgent):
    """总结分析 Agent"""

    name = "SummaryAgent"
    description = "综合分析并输出最终投资结论：汇总调研结果，识别关键判断与风险"
    tool_names = []  # 空 = 使用全部工具（可在综合阶段自行核实关键数据）
    system_prompt = SYSTEM_PROMPT
    max_iterations = 8

    def run_research(
        self,
        query: str,
        assets: List[Asset],
        agent_results: List[AgentResult],
        risk_preference: str = "",
        session_id: str = "",
    ) -> InvestmentAnswer:
        """综合分析调研结果，输出投资答案"""
        events.agent_started(self.task_id, self.name, query, "综合调研结果并输出最终结论")

        research_summary = self._build_research_context(agent_results)
        task = AgentTask(
            agent_name=self.name,
            goal=query,
            assets=assets,
            context=research_summary,
            risk_preference=risk_preference,
        )

        from agents.loop import ReActLoop

        loop = ReActLoop(
            client=self._get_client(),
            model=self._get_model(),
            system_prompt=self.system_prompt,
            tool_schemas=self._get_tool_schemas(),
            execute_tool=self._execute_tool,
            task_id=self.task_id,
            agent_name=self.name,
            max_iterations=self.max_iterations,
            max_tokens=16384,  # 研报较长，需更大输出空间（含 summary/key_points/多空论据/风险等）
            keep_full_json=True,  # 保留模型输出的完整 JSON 结构，供 _parse_answer 解析全部章节
        )

        try:
            result = loop.run(self._build_user_message(task))
            answer = self._parse_answer(result, query, assets, session_id)
        except Exception as e:
            logger.exception("[SummaryAgent] 综合分析失败: %s", e)
            events.agent_failed(self.task_id, self.name, str(e))
            answer = InvestmentAnswer(
                session_id=session_id,
                query=query,
                assets=assets,
                summary=f"综合分析过程中发生错误: {e}",
                risks=["分析流程异常"],
            )

        events.agent_completed(
            self.task_id, self.name,
            result_summary=answer.summary,
            evidence_refs=answer.evidence_refs,
        )
        events.final_answer(self.task_id, answer.model_dump())
        return answer

    @staticmethod
    def _build_research_context(agent_results: List[AgentResult]) -> str:
        """将各调研 Agent 结果组装成上下文"""
        if not agent_results:
            return "（无调研结果）"
        parts = []
        for r in agent_results:
            parts.append(f"## {r.agent_name} 调研结论")
            parts.append(r.conclusion or "（无结论）")
            if r.thinking_log:
                parts.append("思考轨迹：")
                parts.extend(f"- {t}" for t in r.thinking_log[-3:])
        return "\n\n".join(parts)

    def _parse_answer(
        self,
        result: AgentResult,
        query: str,
        assets: List[Asset],
        session_id: str,
    ) -> InvestmentAnswer:
        """从 AgentResult 解析出 InvestmentAnswer"""
        conclusion = result.conclusion or ""
        data = self._extract_answer_json(conclusion)

        if data:
            summary = str(data.get("summary") or conclusion)
            key_points = [str(x) for x in data.get("key_points", []) if x]
            risks = [str(x) for x in data.get("risks", []) if x]
            reasoning = str(data.get("reasoning") or "")
            information_gaps = [str(x) for x in data.get("information_gaps", []) if x]
            time_frame = str(data.get("time_frame") or "")
            model_confidence = data.get("confidence")
            bull_cases = self._parse_cases(data.get("bull_cases"))
            bear_cases = self._parse_cases(data.get("bear_cases"))
            structured_risks = self._parse_structured_risks(data.get("structured_risks"), risks)
        else:
            summary = conclusion
            key_points = self._split_points(conclusion)
            risks = []
            reasoning = ""
            information_gaps = []
            time_frame = ""
            model_confidence = None
            bull_cases = []
            bear_cases = []
            structured_risks = []

        # 深度字段兜底：模型可能只输出 summary 文本，尝试从结论提取
        if not key_points and summary:
            key_points = self._split_points(summary)
        if not time_frame:
            time_frame = self._extract_time_frame(conclusion)

        # 置信度评分：综合模型自评 + degraded + 信息缺口数 + 工具失败率
        confidence = self._compute_confidence(
            model_confidence=model_confidence,
            degraded=result.degraded,
            information_gaps=information_gaps,
            tool_calls=result.tool_calls,
            bull_cases=bull_cases,
            bear_cases=bear_cases,
        )

        return InvestmentAnswer(
            session_id=session_id,
            query=query,
            assets=assets,
            summary=summary,
            key_points=key_points,
            risks=risks,
            structured_risks=structured_risks,
            evidence_refs=result.evidence_refs,
            confidence=confidence,
            reasoning=reasoning,
            bull_cases=bull_cases,
            bear_cases=bear_cases,
            information_gaps=information_gaps,
            time_frame=time_frame,
        )

    @staticmethod
    def _parse_structured_risks(raw: Any, fallback_risks: List[str]) -> List[Dict[str, Any]]:
        """
        解析结构化风险列表。

        Args:
            raw: 模型输出的 structured_risks（dict 列表）
            fallback_risks: 字符串风险列表（当 raw 无效时作为兜底，转为 type=其他）

        Returns:
            结构化风险列表 [{type, desc, probability, impact, priced_in}]
        """
        result: List[Dict[str, Any]] = []
        if isinstance(raw, list):
            for item in raw:
                if not isinstance(item, dict):
                    continue
                desc = str(item.get("desc") or item.get("description") or item.get("风险") or "").strip()
                if not desc:
                    continue
                rtype = str(item.get("type") or item.get("类型") or "其他").strip()
                prob = str(item.get("probability") or item.get("概率") or "medium").strip().lower()
                impact = str(item.get("impact") or item.get("影响") or "medium").strip().lower()
                priced_in = item.get("priced_in")
                if prob not in ("high", "medium", "low"):
                    prob = "medium"
                if impact not in ("high", "medium", "low"):
                    impact = "medium"
                result.append({
                    "type": rtype,
                    "desc": desc,
                    "probability": prob,
                    "impact": impact,
                    "priced_in": bool(priced_in) if priced_in is not None else None,
                })
        # 兜底：无结构化风险时，把字符串风险转成 type=其他
        if not result:
            for risk in fallback_risks or []:
                result.append({
                    "type": "其他",
                    "desc": str(risk),
                    "probability": "medium",
                    "impact": "medium",
                    "priced_in": None,
                })
        return result

    @staticmethod
    def _parse_cases(raw: Any) -> List[Dict[str, Any]]:
        """解析 bull_cases / bear_cases（兼容 dict 列表 / 字符串列表）"""
        cases: List[Dict[str, Any]] = []
        if not raw:
            return cases
        for item in raw:
            if isinstance(item, dict):
                point = str(item.get("point") or item.get("text") or item.get("论据") or "").strip()
                if not point:
                    continue
                strength = str(item.get("strength") or item.get("强度") or "medium").strip().lower()
                if strength not in ("high", "medium", "low"):
                    strength = "medium"
                source = str(item.get("source") or item.get("来源") or "").strip()
                cases.append({"point": point, "strength": strength, "source": source})
            elif isinstance(item, str) and item.strip():
                cases.append({"point": item.strip(), "strength": "medium", "source": ""})
        return cases

    @staticmethod
    def _compute_confidence(
        model_confidence: Optional[float],
        degraded: bool,
        information_gaps: List[str],
        tool_calls: List[Any],
        bull_cases: List[Dict[str, Any]],
        bear_cases: List[Dict[str, Any]],
    ) -> float:
        """
        综合置信度评分（0~1）：
        - 基准:模型自评（0~1），无自评用 0.85
        - degraded → 直接压到 ≤0.4
        - 信息缺口 ≥3 扣 0.1；≥5 再扣 0.1
        - 工具失败率 >50% 扣 0.1
        - 多空论据过于失衡（单边论据数为 0）扣 0.05
        """
        base = 0.85
        if isinstance(model_confidence, (int, float)):
            base = float(model_confidence)
        base = max(0.0, min(1.0, base))

        if degraded:
            return min(base, 0.4)

        if len(information_gaps or []) >= 5:
            base -= 0.2
        elif len(information_gaps or []) >= 3:
            base -= 0.1

        if tool_calls:
            total = len(tool_calls)
            failed = sum(1 for t in tool_calls if getattr(t, "status", "") == "failed")
            if total > 0 and failed / total > 0.5:
                base -= 0.1

        # 论据失衡惩罚：要求双方至少各 1 条论据
        if not bull_cases or not bear_cases:
            base -= 0.05

        return max(0.0, min(1.0, round(base, 2)))

    @staticmethod
    def _extract_answer_json(text: str) -> Optional[Dict[str, Any]]:
        """
        从文本中提取最终答案 JSON（容错解析）

        解析策略（按优先级）：
        1. 贪婪匹配到最后一个 `}`：适用于 JSON 内部含 `}`（如 Markdown/嵌套对象）或尾部带说明文字
        2. 非贪婪匹配第一个对象：适用于文本中存在多个 JSON 片段
        3. 截断修复：贪婪匹配到 `{` 但 JSON 未闭合（LLM 输出被 max_tokens 截断）时，
           尝试补齐括号后解析，尽可能保留已生成的 summary 内容
        仅接受带 final/answer 类 decision 字段的对象
        """
        if not text:
            return None

        def _is_answer(data: Dict[str, Any]) -> bool:
            return str(data.get("decision", "")).lower() in (
                "final", "final_answer", "done", "answer",
            )

        # 1/2. 标准匹配
        for pattern in (r"\{[\s\S]*\}", r"\{[\s\S]*?\}"):
            match = re.search(pattern, text)
            if not match:
                continue
            try:
                data = json.loads(match.group(0))
                if _is_answer(data):
                    return data
            except json.JSONDecodeError:
                continue

        # 3. 截断修复：找到最外层 `{`，从该位置向后补全括号
        start = text.find("{")
        if start == -1:
            return None
        try:
            repaired = SummaryAgent._repair_truncated_json(text[start:])
            if repaired:
                data = json.loads(repaired)
                if _is_answer(data):
                    return data
        except (json.JSONDecodeError, ValueError):
            pass
        return None

    @staticmethod
    def _repair_truncated_json(fragment: str) -> Optional[str]:
        """
        尝试修复被截断的 JSON：从片段开头逐字符扫描，
        维护括号/字符串状态，若截断在字符串内部（引号未闭合），
        先补齐字符串与右括号；否则按括号深度补齐。
        仅当片段含完整的 decision 键时返回修复结果。
        """
        depth = 0
        in_string = False
        escape = False
        last_valid_end = None
        truncated_in_string = False
        for i, ch in enumerate(fragment):
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch in "{[":
                depth += 1
            elif ch in "}]":
                depth -= 1
                if depth == 0 and last_valid_end is None:
                    last_valid_end = i + 1
            elif ch == "\n":
                if depth > 0:
                    break
        # 截断发生在字符串内部（循环结束仍 in_string）→ 补齐闭合引号
        if in_string:
            fragment = fragment.rstrip() + '"'
            truncated_in_string = True
            # 重新扫描一次（引号补上后括号状态可能变化）
            depth = 0
            in_string = False
            escape = False
            last_valid_end = None
            for ch in fragment:
                if in_string:
                    if escape:
                        escape = False
                    elif ch == "\\":
                        escape = True
                    elif ch == '"':
                        in_string = False
                    continue
                if ch == '"':
                    in_string = True
                elif ch in "{[":
                    depth += 1
                elif ch in "}]":
                    depth -= 1
                    if depth == 0 and last_valid_end is None:
                        last_valid_end = len(fragment)
        # 补齐右括号
        candidate = fragment
        if depth > 0:
            candidate = fragment + "}" * depth
        if last_valid_end and not truncated_in_string:
            candidate = fragment[:last_valid_end]
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            # 再试:从后向前截取可解析的最长前缀
            for split in range(len(candidate), 0, -1):
                piece = candidate[:split]
                if piece.count("{") - piece.count("}") > 0:
                    repaired = piece + "}" * (piece.count("{") - piece.count("}"))
                    try:
                        json.loads(repaired)
                        return repaired
                    except json.JSONDecodeError:
                        continue
            return None

    @staticmethod
    def _extract_time_frame(text: str) -> str:
        """从结论文本中提取时间框架关键词"""
        if not text:
            return ""
        keywords = ["短期", "中期", "长期", "短线", "波段", "中长期"]
        for kw in keywords:
            if kw in text:
                return kw
        return ""

    @staticmethod
    def _split_points(text: str) -> List[str]:
        """粗拆分文本为要点列表"""
        points = []
        for line in re.split(r"[\n。；;]", text):
            line = line.strip()
            if len(line) >= 8 and line not in points:
                points.append(line)
            if len(points) >= 5:
                break
        return points
