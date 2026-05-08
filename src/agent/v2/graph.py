#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LangGraph 动态编排核心
定义 V2 的图结构和节点连接
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from langgraph.graph import StateGraph, END

from agent.v2.state import InvestmentState
from agent.v2.context_loader import load_context
from agent.v2.router_agent import route_intent
from agent.v2.asset_resolver import resolve_assets
from agent.v2.planner_agent import plan_tasks
from agent.v2.executor import execute_tools
from agent.v2.evidence_agent import collect_evidence
from agent.v2.answer_agent import draft_answer, compose_answer
from agent.v2.critic_agent import critic_check, should_revise, revise_answer
from agent.v2.compliance_agent import compliance_check, should_block, safe_response
from agent.v2.memory_agent import finalize_answer, save_memory

logger = logging.getLogger(__name__)

MAX_ITERATIONS = int(os.getenv("AGENT_V2_MAX_ITERATIONS", "6"))
REQUIRE_CRITIC = os.getenv("AGENT_V2_REQUIRE_CRITIC", "true").lower() == "true"
REQUIRE_COMPLIANCE = os.getenv("AGENT_V2_REQUIRE_COMPLIANCE", "true").lower() == "true"


def should_continue_execution(state: InvestmentState) -> str:
    """条件边：是否需要重新规划"""
    if state.replan_count >= 2:
        return "collect"
    
    failed_tools = [r for r in state.tool_results if r.status == "failed"]
    critical_tools = [r for r in failed_tools if r.tool_name in ("cn_stock_history", "analysis")]
    
    if critical_tools and state.replan_count < 2:
        return "replan"
    
    return "collect"


def build_graph() -> StateGraph:
    """
    构建 V2 执行图
    
    图结构：
    load_context -> route_intent -> resolve_assets -> plan_tasks -> execute_tools
    -> should_continue? -> collect_evidence -> draft_answer -> critic_check
    -> should_revise? -> compose_answer -> compliance_check -> should_block?
    -> save_memory -> END
    """
    workflow = StateGraph(InvestmentState)

    workflow.add_node("load_context", load_context)
    workflow.add_node("route_intent", route_intent)
    workflow.add_node("resolve_assets", resolve_assets)
    workflow.add_node("plan_tasks", plan_tasks)
    workflow.add_node("execute_tools", execute_tools)
    workflow.add_node("collect_evidence", collect_evidence)
    workflow.add_node("draft_answer", draft_answer)
    workflow.add_node("critic_check", critic_check)
    workflow.add_node("revise_answer", revise_answer)
    workflow.add_node("compose_answer", compose_answer)
    workflow.add_node("compliance_check", compliance_check)
    workflow.add_node("safe_response", safe_response)
    workflow.add_node("finalize_answer", finalize_answer)
    workflow.add_node("save_memory", save_memory)

    workflow.set_entry_point("load_context")

    workflow.add_edge("load_context", "route_intent")
    workflow.add_edge("route_intent", "resolve_assets")
    workflow.add_edge("resolve_assets", "plan_tasks")
    workflow.add_edge("plan_tasks", "execute_tools")

    workflow.add_conditional_edges(
        "execute_tools",
        should_continue_execution,
        {
            "replan": "plan_tasks",
            "collect": "collect_evidence",
        },
    )

    workflow.add_edge("collect_evidence", "draft_answer")
    workflow.add_edge("draft_answer", "critic_check")

    workflow.add_conditional_edges(
        "critic_check",
        should_revise,
        {
            "revise": "revise_answer",
            "compliance": "compose_answer",
        },
    )

    workflow.add_edge("revise_answer", "compose_answer")
    workflow.add_edge("compose_answer", "compliance_check")

    workflow.add_conditional_edges(
        "compliance_check",
        should_block,
        {
            "block": "safe_response",
            "final": "finalize_answer",
        },
    )

    workflow.add_edge("safe_response", "save_memory")
    workflow.add_edge("finalize_answer", "save_memory")
    workflow.add_edge("save_memory", END)

    return workflow


def compile_graph():
    """编译图"""
    graph = build_graph()
    return graph.compile()


def run_v2_query(
    session_id: str,
    user_id: int,
    query: str,
    chat_history: list = None,
    user_profile: dict = None,
) -> Dict[str, Any]:
    """
    执行 V2 查询
    
    Args:
        session_id: 会话ID
        user_id: 用户ID
        query: 用户查询
        chat_history: 聊天历史
        user_profile: 用户信息
        
    Returns:
        执行结果
    """
    logger.info("run_v2_query: session=%s, query=%s", session_id, query[:50])

    initial_state = InvestmentState(
        session_id=session_id,
        user_id=user_id,
        query=query,
        chat_history=chat_history or [],
        user_profile=user_profile or {},
    )

    app = compile_graph()

    try:
        final_state = app.invoke(initial_state)

        if isinstance(final_state, dict):
            investment_answer = final_state.get("investment_answer")
            result = {
                "session_id": session_id,
                "final_answer": final_state.get("final_answer", ""),
                "investment_answer": investment_answer.model_dump() if investment_answer and hasattr(investment_answer, "model_dump") else None,
                "degraded": final_state.get("degraded", False),
                "errors": final_state.get("errors", []),
                "trace": final_state.get("trace", []),
                "assets": [a.model_dump() if hasattr(a, "model_dump") else a for a in final_state.get("assets", [])],
                "evidence_items": [e.model_dump() if hasattr(e, "model_dump") else e for e in final_state.get("evidence_items", [])],
                "tool_results": [r.model_dump() if hasattr(r, "model_dump") else r for r in final_state.get("tool_results", [])],
            }
            _persist_observability(result, user_id)
            return result
        else:
            investment_answer = final_state.investment_answer
            result = {
                "session_id": session_id,
                "final_answer": final_state.final_answer or "",
                "investment_answer": investment_answer.model_dump() if investment_answer else None,
                "degraded": final_state.degraded,
                "errors": final_state.errors,
                "trace": final_state.trace,
                "assets": [a.model_dump() for a in final_state.assets],
                "evidence_items": [e.model_dump() for e in final_state.evidence_items],
                "tool_results": [r.model_dump() for r in final_state.tool_results],
            }
            _persist_observability(result, user_id)
            return result
    except Exception as e:
        logger.error("V2 执行失败: %s", e)
        return {
            "session_id": session_id,
            "final_answer": f"系统执行异常: {str(e)}",
            "investment_answer": None,
            "degraded": True,
            "errors": [str(e)],
            "trace": [],
            "assets": [],
            "evidence_items": [],
            "tool_results": [],
        }


def _persist_observability(result: Dict[str, Any], user_id: int) -> None:
    """保存 Agent trace 与工具调用记录，失败时不影响主链路"""
    try:
        import json
        from models import get_db, init_db
        from models.database import AgentTrace, ToolCallRecord
        from utils.log_sanitizer import sanitize_dict, sanitize_log

        init_db()
        session_id = result.get("session_id", "")
        with get_db() as db:
            for item in result.get("trace", []):
                db.add(AgentTrace(
                    session_id=session_id,
                    user_id=user_id,
                    node_name=sanitize_log(str(item.get("node", ""))),
                    status=sanitize_log(str(item.get("status", ""))),
                    input_summary=sanitize_log(str(item.get("input_summary", ""))),
                    output_summary=sanitize_log(str(item.get("output_summary", ""))),
                    latency_ms=int(item.get("latency_ms", 0) or 0),
                ))

            for item in result.get("tool_results", []):
                safe_data = sanitize_dict(item.get("data", {})) if isinstance(item.get("data"), dict) else {}
                db.add(ToolCallRecord(
                    session_id=session_id,
                    tool_name=sanitize_log(str(item.get("tool_name", ""))),
                    params_json=None,
                    status=sanitize_log(str(item.get("status", ""))),
                    result_summary=json.dumps(safe_data, ensure_ascii=False)[:2000],
                    error=sanitize_log(str(item.get("error", ""))) if item.get("error") else None,
                    latency_ms=int(item.get("latency_ms", 0) or 0),
                ))
            db.commit()
    except Exception as e:
        logger.warning("保存 V2 可观测记录失败: %s", e)
