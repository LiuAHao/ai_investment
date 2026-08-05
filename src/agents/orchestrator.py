#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
总编排 Agent（Supervisor）
负责：
1. 通过 AssetResolveTool 识别资产与意图
2. 决策派发哪些调研 Agent（按需调度，LLM 判断 + 关键词规则兜底）
3. 线程池并行执行调研 Agent
4. 汇总结果交给 SummaryAgent
"""

from __future__ import annotations

import concurrent.futures
import logging
import re
from typing import Any, Dict, List, Optional

from utils.llm_common import build_client, get_env
from agents import events
from agents.state import AgentResult, AgentTask, Asset, InvestmentAnswer

logger = logging.getLogger(__name__)

# 规则兜底关键词 → Agent 派发
_KEYWORD_PLAN: List[Dict[str, Any]] = [
    {
        "keywords": ["环境", "大盘", "宏观", "市场", "指数", "行情", "趋势", "情绪"],
        "agents": ["MarketAgent", "NewsAgent"],
        "reason": "宏观市场问题：行情 + 新闻两路调研",
    },
    {
        "keywords": ["基金", "ETF", "股票", "个股", "买入", "分析", "走势", "估值"],
        "agents": ["MarketAgent", "NewsAgent", "KnowledgeAgent"],
        "reason": "具体资产问题：行情 + 新闻 + 知识三路调研",
    },
    {
        "keywords": [
            "框架", "方法", "逻辑", "概念", "定义", "指标", "口径",
            "合规", "规则", "市盈率", "PE", "ROE", "估值", "基本面",
            "什么是", "怎么算", "如何分析",
        ],
        "agents": ["KnowledgeAgent"],
        "reason": "知识类问题：知识库调研",
    },
]


class OrchestratorAgent:
    """总编排 Agent"""

    name = "OrchestratorAgent"

    def __init__(self, task_id: str = "", model: Optional[str] = None):
        self.task_id = task_id
        self._client = None
        self._model = model or get_env("AGENT_LLM_MODEL", "deepseek-chat")

    # ---------- 主入口 ----------

    def run_query(
        self,
        session_id: str,
        query: str,
        risk_preference: str = "",
        context: str = "",
    ) -> Dict[str, Any]:
        """执行完整研究流程"""
        # 1. 编排思考：理解问题
        events.orchestrator_thinking(self.task_id, f"识别问题意图：{query[:60]}")
        assets = self._resolve_assets(query, context)

        # 2. 决策派发计划
        plan = self._decide_plan(query, assets)
        events.orchestrator_thinking(
            self.task_id,
            f"确定研究计划：{' + '.join(plan['agents'])}（{plan['reason']}）",
        )
        events.orchestrator_decided(self.task_id, plan["agents"], plan["reason"])

        # 3. 并行执行调研 Agent
        agent_results = self._run_research_agents(plan["agents"], query, assets, context)

        # 4. 汇总交给 SummaryAgent
        from agents.summary_agent import SummaryAgent

        summary_agent = SummaryAgent(task_id=self.task_id)
        answer = summary_agent.run_research(
            query=query,
            assets=assets,
            agent_results=agent_results,
            risk_preference=risk_preference,
            session_id=session_id,
        )

        # 5. L3 沉淀：将研究结论蒸馏为可复用知识写回知识库（带质量管控，失败不影响主流程）
        self._sediment_research(answer)

        return {
            "query": query,
            "assets": [a.model_dump() for a in assets],
            "plan": plan,
            "agent_results": [r.model_dump() for r in agent_results],
            "answer": answer.model_dump(),
        }

    # ---------- 资产识别 ----------

    def _resolve_assets(self, query: str, context: str = "") -> List[Asset]:
        """识别资产（规则优先，无需 LLM）"""
        try:
            from tools.registry import get_tool_registry
            registry = get_tool_registry()
            result = registry.execute("asset_resolve", {"query": query})

            selected = result.data.get("selected_assets", [])
            if selected:
                assets = [Asset(**a) for a in selected]
                names = ", ".join(a.name or a.symbol or "" for a in assets)
                events.orchestrator_thinking(self.task_id, f"资产识别：{names}")
                return assets

            # 追问继承
            if context:
                # 尝试从上下文提取资产（简化：交给规则，无资产时返回空）
                pass

            events.orchestrator_thinking(self.task_id, "未识别到具体资产，按宏观/市场问题处理")
            return []
        except Exception as e:
            logger.warning("资产解析失败: %s", e)
            events.orchestrator_thinking(self.task_id, f"资产解析异常：{e}")
            return []

    # ---------- 派发计划（LLM + 规则兜底） ----------

    def _decide_plan(self, query: str, assets: List[Asset]) -> Dict[str, Any]:
        """决策调研 Agent 派发计划"""
        # 优先 LLM 决策
        llm_plan = self._decide_plan_by_llm(query, assets)
        if llm_plan:
            return llm_plan

        # 规则兜底
        return self._decide_plan_by_rule(query)

    def _decide_plan_by_llm(self, query: str, assets: List[Asset]) -> Optional[Dict[str, Any]]:
        """LLM 决策派发计划"""
        try:
            client = self._get_client()
            asset_desc = ", ".join(f"{a.name or a.symbol}({a.asset_type.value})" for a in assets) or "无具体资产（宏观问题）"
            prompt = (
                "你是投资研究编排器。根据用户问题和识别到的资产，决定需要启动哪些调研 Agent。\n"
                f"用户问题：{query}\n"
                f"识别资产：{asset_desc}\n\n"
                "可选 Agent：\n"
                "- MarketAgent：市场行情/财务数据调研\n"
                "- NewsAgent：新闻/舆情调研\n"
                "- KnowledgeAgent：知识库/基本面调研\n\n"
                "输出 JSON：{\"agents\": [\"Agent名\", ...], \"reason\": \"理由\"}\n"
                "只输出 JSON，不要其他内容。"
            )
            response = client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
            )
            content = ""
            if response.choices:
                content = getattr(response.choices[0].message, "content", None) or ""
            import json
            match = re.search(r"\{[\s\S]*?\}", content)
            if not match:
                return None
            data = json.loads(match.group(0))
            agents = [a for a in data.get("agents", []) if a in ("MarketAgent", "NewsAgent", "KnowledgeAgent")]
            if not agents:
                return None
            return {"agents": agents, "reason": str(data.get("reason", "LLM 决策"))}
        except Exception as e:
            logger.warning("LLM 派发决策失败，走规则兜底: %s", e)
            return None

    def _decide_plan_by_rule(self, query: str) -> Dict[str, Any]:
        """规则兜底：关键词匹配"""
        for rule in _KEYWORD_PLAN:
            if any(kw in query for kw in rule["keywords"]):
                return {"agents": rule["agents"], "reason": rule["reason"]}
        # 默认全派
        return {
            "agents": ["MarketAgent", "NewsAgent", "KnowledgeAgent"],
            "reason": "默认三路调研",
        }

    # ---------- 并行执行调研 Agent ----------

    def _run_research_agents(
        self,
        agent_names: List[str],
        query: str,
        assets: List[Asset],
        context: str,
    ) -> List[AgentResult]:
        """线程池并行执行调研 Agent"""
        from agents.research.market_agent import MarketAgent
        from agents.research.news_agent import NewsAgent
        from agents.research.knowledge_agent import KnowledgeAgent

        agent_map = {
            "MarketAgent": MarketAgent,
            "NewsAgent": NewsAgent,
            "KnowledgeAgent": KnowledgeAgent,
        }

        results: List[AgentResult] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            future_map = {}
            for name in agent_names:
                cls = agent_map.get(name)
                if not cls:
                    continue
                agent = cls(task_id=self.task_id)
                task = AgentTask(
                    agent_name=name,
                    goal=query,
                    assets=assets,
                    context=context,
                )
                future = pool.submit(agent.run, task)
                future_map[future] = name

            for future in concurrent.futures.as_completed(future_map):
                name = future_map[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.exception("[%s] 执行异常: %s", name, e)
                    results.append(AgentResult(agent_name=name, conclusion="", error=str(e), degraded=True))

        # 按计划顺序排序
        order = {name: idx for idx, name in enumerate(agent_names)}
        results.sort(key=lambda r: order.get(r.agent_name, 99))
        return results

    # ---------- L3 知识沉淀 ----------

    def _sediment_research(self, answer: Any) -> None:
        """
        将研究结论蒸馏为可复用知识写入知识库（L3 沉淀）。

        使用质量管控管线：质量门槛 → LLM 蒸馏 → 相似度查重 → 分层写入 → 生命周期。
        沉淀失败/被拒绝均不影响研究主流程，只记录日志。
        """
        try:
            from rag.indexer import sediment_research

            degraded = False
            has_evidence = bool(answer.evidence_refs)
            # 结论为空则视为降级，阻止沉淀
            if not (answer.summary or "").strip():
                degraded = True

            result = sediment_research(
                summary=answer.summary or "",
                key_points=list(answer.key_points or []),
                reasoning=answer.reasoning or "",
                query=answer.query or "",
                degraded=degraded,
                has_evidence=has_evidence,
                confidence=float(getattr(answer, "confidence", 0.0) or 0.0),
                time_frame=getattr(answer, "time_frame", "") or "",
            )
            status = result.get("status", "error")
            if status == "written":
                events.orchestrator_thinking(
                    self.task_id,
                    f"L3 知识沉淀完成：{result.get('title', '')}",
                )
            else:
                logger.info("L3 沉淀未写入（%s）：%s", status, result.get("reason", ""))
        except Exception as exc:
            logger.exception("L3 知识沉淀异常（不影响主流程）: %s", exc)

    # ---------- 基础设施 ----------

    def _get_client(self):
        if self._client is None:
            self._client = build_client()
        return self._client
