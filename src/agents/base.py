#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
BaseReActAgent 基类

职责：
1. 组装 system prompt 与工具白名单
2. 执行 ReAct 循环（loop.py）
3. 工具执行结果自动登记到 EvidenceLedger
4. 发射 agent_* / tool_* 事件

注：v4 起不再有"共享发现池"与"两轮补充调研"，跨 Agent 信息通过 Ledger 只读共享。
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

from openai import OpenAI

from agents import events
from agents.loop import ReActLoop
from agents.state import AgentResult, AgentTask, ToolResult
from utils.llm_common import build_client, get_env

logger = logging.getLogger(__name__)

# 回测模式无法 point-in-time 的工具
NEWS_TOOLS = {"asset_news_search", "web_research"}

# 同一标的只需取一次的工具（重复调用不会产生新信息，直接复用）
SINGLETON_TOOLS = {
    "stock_valuation_band",
    "stock_financial_summary",
    "stock_financial_indicator",
    "stock_peer_compare",
    "stock_fund_flow",
    "stock_expectation",
    "stock_events",
    "industry_context",
    "index_environment",
    "macro_indicator",
}


class BaseReActAgent:
    """ReAct Agent 基类"""

    name: str = ""
    description: str = ""
    tool_names: List[str] = []
    system_prompt: str = ""
    max_iterations: int = 6
    stage: str = "L1"
    keep_full_json: bool = False
    max_tokens: int = 8192
    final_instruction: Optional[str] = None

    def __init__(
        self,
        task_id: str = "",
        model: Optional[str] = None,
        ledger: Optional[Any] = None,
        budget: Optional[Any] = None,
        as_of: Optional[str] = None,
    ):
        self.task_id = task_id
        self._client: Optional[OpenAI] = None
        self._model = model
        self._tool_schemas_cache: Optional[List[Dict[str, Any]]] = None
        self.max_iterations = self._resolve_max_iterations()
        self.ledger = ledger
        self.budget = budget
        self.as_of = as_of
        self._tool_cache: Dict[tuple, ToolResult] = {}
        self._singleton_cache: Dict[tuple, ToolResult] = {}

    def _resolve_max_iterations(self) -> int:
        raw = os.getenv("AGENT_MAX_ITERATIONS", "").strip()
        if raw.isdigit() and int(raw) > 0:
            return int(raw)
        return self.__class__.max_iterations

    # ---------- 入口 ----------

    def run(self, task: AgentTask, shared_pool: Optional[Any] = None) -> AgentResult:
        """执行 Agent 任务（shared_pool 参数仅为兼容旧调用，已废弃）"""
        self._current_assets = list(getattr(task, "assets", []) or [])
        events.agent_started(
            self.task_id, self.name, task.goal, task.goal,
            round=1, stage=self.stage,
        )

        loop = ReActLoop(
            client=self._get_client(),
            model=self._get_model(),
            system_prompt=self._build_prompt(task),
            tool_schemas=self._get_tool_schemas(),
            execute_tool=self._execute_tool,
            task_id=self.task_id,
            agent_name=self.name,
            max_iterations=self.max_iterations,
            on_tool_result=self._on_tool_result,
            budget=self.budget,
            keep_full_json=self.keep_full_json,
            max_tokens=self.max_tokens,
            final_instruction=self.final_instruction,
        )

        try:
            result = loop.run(self._build_user_message(task))
            events.agent_completed(
                self.task_id, self.name,
                result_summary=result.conclusion,
                evidence_refs=result.evidence_refs,
                round=1,
                stage=self.stage,
            )
            return result
        except Exception as e:  # noqa: BLE001  (单路失败不能中断编排)
            logger.exception("[%s] Agent 执行失败: %s", self.name, e)
            events.agent_failed(self.task_id, self.name, str(e))
            return AgentResult(
                agent_name=self.name,
                conclusion=f"研究过程中发生错误: {e}",
                error=str(e),
                thinking_log=[],
                degraded=True,
            )

    # ---------- 子类可覆盖 ----------

    def _build_prompt(self, task: AgentTask) -> str:
        return self.system_prompt

    def _build_user_message(self, task: AgentTask) -> str:
        parts = [f"研究目标：{task.goal}"]
        if task.assets:
            names = ", ".join(a.name or a.symbol or "" for a in task.assets)
            parts.append(f"涉及资产：{names}")
        if task.context:
            parts.append(f"上下文：\n{task.context}")
        if task.risk_preference:
            parts.append(f"用户风险偏好：{task.risk_preference}")
        if self.as_of:
            parts.append(f"决策时点：{self.as_of}（不得使用该日期之后的数据）")
        return "\n".join(parts)

    # ---------- 工具 ----------

    def _get_tool_schemas(self) -> List[Dict[str, Any]]:
        if self._tool_schemas_cache is not None:
            return self._tool_schemas_cache
        from tools.registry import get_tool_registry

        registry = get_tool_registry()
        schemas = []
        for spec in registry.get_all_specs():
            if self.tool_names and spec.name not in self.tool_names:
                continue
            schemas.append(spec.model_dump())
        self._tool_schemas_cache = schemas
        return schemas

    def _execute_tool(self, tool_name: str, params: Dict[str, Any]) -> ToolResult:
        import hashlib as _hashlib
        import json as _json
        import time as _time

        started = _time.time()
        result = self._asset_guard(tool_name, params) or self._execute_tool_inner(tool_name, params)
        try:
            from obs.context import current as _obs_current
            from obs.store import get_store

            ctx = _obs_current()
            task_id = ctx.get("task_id", "") or getattr(self, "task_id", "")
            if task_id:
                data = result.data or {}
                serialized = _json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
                get_store().record_tool(
                    task_id,
                    ctx.get("stage", "") or getattr(self, "stage", ""),
                    ctx.get("agent", "") or getattr(self, "name", ""),
                    tool_name,
                    params,
                    int((_time.time() - started) * 1000),
                    result.status,
                    result.error or "",
                    len(serialized),
                    _hashlib.sha1(serialized.encode()).hexdigest()[:16],
                )
        except Exception:
            pass
        return result

    def _execute_tool_inner(self, tool_name: str, params: Dict[str, Any]) -> ToolResult:
        if self.tool_names and tool_name not in self.tool_names:
            return ToolResult(
                tool_name=tool_name,
                status="failed",
                error=f"工具 {tool_name} 不在本 Agent 白名单中",
                confidence=0.0,
            )
        if tool_name in NEWS_TOOLS:
            from utils import pit

            if pit.news_blocked():
                return ToolResult(
                    tool_name=tool_name,
                    status="skipped",
                    error="回测模式：新闻类数据源无法 point-in-time，已禁用",
                    confidence=0.0,
                )
        singleton_key = (
            tool_name,
            str((params or {}).get("symbol") or (params or {}).get("fund_code") or ""),
        )
        if tool_name in SINGLETON_TOOLS:
            single = self._singleton_cache.get(singleton_key)
            if single is not None:
                data = dict(single.data or {})
                data["_cache_hit"] = True
                data["_note"] = "同一标的的该工具已调用过，直接复用第一次结果，不要重复调用"
                return single.model_copy(update={"data": data})

        cache_key = (
            tool_name,
            json.dumps(params or {}, sort_keys=True, ensure_ascii=False, default=str),
        )
        cached = self._tool_cache.get(cache_key)
        if cached is not None:
            data = dict(cached.data or {})
            data["_cache_hit"] = True
            data["_note"] = "相同参数已在本轮调用过，结果直接复用，不要重复调用"
            return cached.model_copy(update={"data": data})

        if self.budget is not None and not self.budget.spend_tool():
            return ToolResult(
                tool_name=tool_name,
                status="skipped",
                error="工具调用预算已耗尽",
                confidence=0.0,
            )
        from tools.registry import get_tool_registry

        result = get_tool_registry().execute(tool_name, params)
        if result.status in ("success", "partial", "failed", "skipped"):
            self._tool_cache[cache_key] = result
            if tool_name in SINGLETON_TOOLS:
                self._singleton_cache[singleton_key] = result
        return result

    def _asset_guard(self, tool_name: str, params: Dict[str, Any]) -> Optional[ToolResult]:
        """资产类型不匹配时返回 skipped，避免 ETF/指数调用个股工具产生 failed。"""
        try:
            from tools.registry import get_tool_registry

            registered = get_tool_registry().get(tool_name)
            if registered is None:
                return None
            allowed = getattr(getattr(registered, "spec", None), "asset_types", None) or []
            if not allowed:
                return None
            raw_symbol = str((params or {}).get("symbol") or (params or {}).get("fund_code") or "").strip()
            symbol = raw_symbol.split(".")[0]
            if not symbol:
                schema = getattr(getattr(registered, "spec", None), "input_schema", {}) or {}
                required = set(schema.get("required") or [])
                if {"symbol", "fund_code"} & required:
                    return ToolResult(
                        tool_name=tool_name,
                        status="skipped",
                        error="缺少标的参数，已跳过",
                        confidence=0.0,
                    )
                return None
            assets = getattr(self, "_current_assets", []) or []
            allowed_values = {getattr(item, "value", str(item)) for item in allowed}
            if not assets:
                # 板块 / 宏观任务没有具体标的：个股专用工具跳过，指数/行业/宏观/新闻放行
                if allowed_values and not (allowed_values & {"index", "industry", "macro"}):
                    return ToolResult(
                        tool_name=tool_name,
                        status="skipped",
                        error="板块/宏观任务不适用个股工具",
                        confidence=0.0,
                    )
                return None
            matched = None
            for asset in assets:
                candidates = {
                    str(getattr(asset, "symbol", "")).split(".")[0],
                    str(getattr(asset, "asset_id", "")).split(".")[0],
                }
                if symbol in candidates:
                    matched = asset
                    break
            if matched is None:
                # 任务已有明确标的但工具参数指向别的代码：
                # 指数类工具放行（用于大盘对照），其余按“不在任务范围”跳过
                if "index" in allowed_values:
                    return None
                return ToolResult(
                    tool_name=tool_name,
                    status="skipped",
                    error=f"标的不在本次任务范围（{symbol}），已跳过",
                    confidence=0.0,
                )
            kind = getattr(matched, "asset_type", None)
            kind_value = getattr(kind, "value", str(kind or ""))
            if kind_value and kind_value not in allowed_values:
                return ToolResult(
                    tool_name=tool_name,
                    status="skipped",
                    error=f"{kind_value} 不适用该工具",
                    confidence=0.0,
                )
        except Exception:
            return None
        return None

    def _on_tool_result(
        self,
        tool_name: str,
        params: Dict[str, Any],
        result: ToolResult,
    ) -> List[str]:
        """工具执行后自动登记证据（由 ReActLoop 回调）"""
        if self.ledger is None:
            return []
        try:
            items = self.ledger.record_tool(
                agent=self.name,
                tool_name=tool_name,
                params=params,
                result=result,
            )
            # 工具执行后立即推进前端台账（不等分析师结束）
            for item in items:
                payload = item.model_dump()
                payload["_agent"] = self.name
                events.evidence_added(self.task_id, payload, self.ledger.count())
            return [item.evidence_id for item in items]
        except Exception as exc:  # noqa: BLE001  (登记失败不能影响工具循环)
            logger.warning("[%s] 证据登记失败: %s", self.name, exc)
            return []

    # ---------- 基础设施 ----------

    def _get_client(self) -> OpenAI:
        if self._client is None:
            self._client = build_client(timeout=120.0, max_retries=0)
        return self._client

    def _get_model(self) -> str:
        if self._model:
            return self._model
        return get_env("AGENT_LLM_MODEL", "deepseek-chat")
