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
3. 多空因素权衡：列出看多/看空的主要论据，判断哪方更占优
4. 识别关键风险与不确定性：哪些数据缺失、哪些假设可能被证伪
5. 给出结论的有效时间框架：该判断适用于短期/中期/长期

【工具使用】仅在以下情况调用（一次即可）：
- 发现关键数据矛盾，需要核实（行情/新闻）
- 核心结论缺少证据支撑，需要补一个关键数据点
- 涉及指标口径/规则，需要查知识库确认
其余情况直接基于调研结果分析，不要为调用而调用。

【输出格式】当信息充分时，输出 JSON 格式的最终结论：
{
  "decision": "final",
  "summary": "总体判断（包含核心逻辑链，2-3 句）",
  "key_points": ["关键判断1（带依据）", "关键判断2（带依据）"],
  "risks": ["风险1（含性质，如市场波动/信息时效）", "风险2"],
  "reasoning": "分析推理过程（多空因素权衡的简述）",
  "information_gaps": ["信息缺口/待验证事项"],
  "time_frame": "结论有效期（如：短期1-4周 / 中期1-6月）"
}

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
    tool_names = [
        "asset_news_search",
        "cn_stock_spot_search",
        "investment_framework_search",
    ]
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
        else:
            summary = conclusion
            key_points = self._split_points(conclusion)
            risks = []
            reasoning = ""
            information_gaps = []
            time_frame = ""

        # 深度字段兜底：模型可能只输出 summary 文本，尝试从结论提取
        if not key_points and summary:
            key_points = self._split_points(summary)
        if not time_frame:
            time_frame = self._extract_time_frame(conclusion)

        return InvestmentAnswer(
            session_id=session_id,
            query=query,
            assets=assets,
            summary=summary,
            key_points=key_points,
            risks=risks,
            evidence_refs=result.evidence_refs,
            confidence=1.0 if not result.degraded else 0.5,
            reasoning=reasoning,
            information_gaps=information_gaps,
            time_frame=time_frame,
        )

    @staticmethod
    def _extract_answer_json(text: str) -> Optional[Dict[str, Any]]:
        """
        从文本中提取最终答案 JSON（容错解析）

        解析策略（按优先级）：
        1. 贪婪匹配到最后一个 `}`：适用于 JSON 内部含 `}`（如 Markdown/嵌套对象）或尾部带说明文字
        2. 非贪婪匹配第一个对象：适用于文本中存在多个 JSON 片段
        仅接受带 final/answer 类 decision 字段的对象
        """
        if not text:
            return None
        for pattern in (r"\{[\s\S]*\}", r"\{[\s\S]*?\}"):
            match = re.search(pattern, text)
            if not match:
                continue
            try:
                data = json.loads(match.group(0))
                if str(data.get("decision", "")).lower() in (
                    "final", "final_answer", "done", "answer",
                ):
                    return data
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
