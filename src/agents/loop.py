#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ReAct 循环执行器
实现 "思考 → 行动(工具) → 观察 → 再思考" 的自主循环。

核心机制：
1. 优先使用 function calling（OpenAI 兼容协议）让模型自主选择工具
2. 模型不支持 function calling 时，降级为 JSON 输出解析
3. 循环边界由模型自己决定（输出 final_answer），仅设安全上限
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

from openai import OpenAI

from agents import events
from agents.state import AgentResult, ToolResult

logger = logging.getLogger(__name__)

# 单条工具结果回填给模型的最大字符数（防止多轮后上下文膨胀）
MAX_TOOL_RESULT_CHARS = 6000
# 结构化裁剪档位：字符串上限、数组保留条数
_COMPACT_LEVELS = ((500, 20), (300, 10), (200, 5), (100, 3))
# 工具连续无进展的阈值
NO_PROGRESS_LIMIT = 2
# 连续无法解析输出的阈值
UNKNOWN_LIMIT = 2


class ToolExecutor:
    """工具执行回调接口（由具体 Agent 注入）"""

    def __call__(self, tool_name: str, params: Dict[str, Any]) -> ToolResult:
        raise NotImplementedError


class ReActLoop:
    """
    ReAct 循环
    """

    def __init__(
        self,
        client: OpenAI,
        model: str,
        system_prompt: str,
        tool_schemas: List[Dict[str, Any]],
        execute_tool: ToolExecutor,
        task_id: str,
        agent_name: str,
        max_iterations: int = 8,
        emit_thinking: bool = True,
        temperature: float = 0.3,
        shared_pool: Optional[Any] = None,  # 已废弃：保留参数仅为兼容旧调用
        max_tokens: int = 8192,
        keep_full_json: bool = False,
        final_instruction: Optional[str] = None,
        on_tool_result: Optional[Any] = None,
        budget: Optional[Any] = None,
    ):
        self.client = client
        self.model = model
        self.system_prompt = system_prompt
        self.tool_schemas = tool_schemas
        self.execute_tool = execute_tool
        self.task_id = task_id
        self.agent_name = agent_name
        self.max_iterations = max_iterations
        self.emit_thinking = emit_thinking
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.keep_full_json = keep_full_json  # final 时保留完整 JSON 结构（供下游解析全部章节）
        self.final_instruction = final_instruction  # 强制收敛时要求模型输出的格式
        self.on_tool_result = on_tool_result  # 工具执行后回调（登记证据台账）
        self.budget = budget  # 共享预算（LLM 调用数）
        self._ledger_refs: List[str] = []
        self._tools_supported: Optional[bool] = None  # 缓存 function calling 支持性

        self.messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        self.thinking_log: List[str] = []
        self.tool_results: List[ToolResult] = []

    # ---------- 工具 Schema 处理 ----------

    def _tool_schemas_for_api(self) -> List[Dict[str, Any]]:
        """将内部 schema 转为 OpenAI function calling 格式"""
        result = []
        for schema in self.tool_schemas:
            params = schema.get("input_schema") or {}
            result.append({
                "type": "function",
                "function": {
                    "name": schema.get("name", ""),
                    "description": schema.get("description", ""),
                    "parameters": params or {"type": "object", "properties": {}},
                },
            })
        return result

    # ---------- 主循环 ----------

    def run(self, user_message: str) -> AgentResult:
        """执行 ReAct 循环"""
        self.messages.append({"role": "user", "content": user_message})

        # 单调性检测：连续无新增成功信息的工具调用次数
        no_progress_streak = 0
        # 连续无法解析的模型输出次数
        unknown_streak = 0

        for step in range(self.max_iterations):
            # 预算耗尽：不调用模型，直接用已登记的工具证据收敛
            if self.budget is not None and self.budget.exhausted():
                return AgentResult(
                    agent_name=self.agent_name,
                    conclusion="",
                    evidence_refs=self._collect_evidence_refs(),
                    tool_calls=self.tool_results,
                    thinking_log=self.thinking_log,
                    error="LLM 调用预算耗尽",
                    degraded=True,
                )

            # 带工具调用尝试（仅在首次或确认支持后）
            if self._tools_supported is not False:
                text_answer = self._try_function_calling()
                if text_answer is not None and text_answer != "":
                    # 模型本轮未调用工具，直接给出了文本回答
                    content = text_answer.strip()
                    decision = self._parse_decision(content)
                    if decision["type"] == "final":
                        self._log_thinking("收敛: 已完成调研，整理输出研究结论")
                        return self._build_result(self._final_conclusion(decision, content))
                    if decision["type"] == "tool":
                        unknown_streak = 0
                        self._handle_tool_call(decision.get("tool", ""), decision.get("params", {}))
                        no_progress_streak = self._check_progress(no_progress_streak)
                        if no_progress_streak >= NO_PROGRESS_LIMIT:
                            return self._force_converge("工具连续无新增信息")
                        continue
                    # 无法解析：作为思考记录；较长文本视为有效思考（不累计失败）
                    self._record_unparsed(content)
                    unknown_streak = 0 if len(content.strip()) >= 40 else unknown_streak + 1
                    if unknown_streak >= UNKNOWN_LIMIT:
                        return self._force_converge("模型连续输出无法解析的内容")
                    continue
                if text_answer == "":
                    # 已处理工具调用，继续循环
                    unknown_streak = 0
                    no_progress_streak = self._check_progress(no_progress_streak)
                    if no_progress_streak >= NO_PROGRESS_LIMIT:
                        return self._force_converge("工具连续无新增信息")
                    continue

            # 文本协议路径（function calling 不可用）
            response = self._call_plain()
            content = response or ""
            decision = self._parse_decision(content)

            if decision["type"] == "final":
                self._log_thinking("收敛: 已完成调研，整理输出研究结论")
                return self._build_result(self._final_conclusion(decision, content))

            if decision["type"] == "tool":
                unknown_streak = 0
                self._handle_tool_call(decision.get("tool", ""), decision.get("params", {}))
                no_progress_streak = self._check_progress(no_progress_streak)
                if no_progress_streak >= NO_PROGRESS_LIMIT:
                    return self._force_converge("工具连续无新增信息")
                continue

            # 无法解析：把内容作为思考记录；较长文本视为有效思考
            self._record_unparsed(content)
            unknown_streak = 0 if len(content.strip()) >= 40 else unknown_streak + 1
            if unknown_streak >= UNKNOWN_LIMIT:
                return self._force_converge("模型连续输出无法解析的内容")

        # 达到上限：强制收敛（让模型基于已有数据综合输出，而非直接拼接日志）
        logger.warning("[%s] 达到最大迭代 %d 次，触发强制收敛", self.agent_name, self.max_iterations)
        return self._force_finalize("达到研究迭代上限")

    def _record_unparsed(self, content: str) -> None:
        """记录无法解析的模型输出；只保留最近两条纯文本，避免挤占上下文"""
        self._log_thinking(content)
        self.messages.append({"role": "assistant", "content": content})
        plain = [
            i for i, m in enumerate(self.messages)
            if m.get("role") == "assistant" and not m.get("tool_calls")
        ]
        for i in reversed(plain[:-2]):
            self.messages.pop(i)

    def _build_result(self, conclusion: str) -> AgentResult:
        return AgentResult(
            agent_name=self.agent_name,
            conclusion=conclusion,
            evidence_refs=self._collect_evidence_refs(),
            tool_calls=self.tool_results,
            thinking_log=self.thinking_log,
        )

    def _final_conclusion(self, decision: Dict[str, Any], fallback: str) -> str:
        """
        final 决策的结论文本：
        keep_full_json=True 时保留模型输出的完整 JSON 结构（含 key_points/多空论据/风险等），
        供下游 _parse_answer 解析出全部章节；否则只取 summary 文本。
        """
        if self.keep_full_json and decision.get("raw") is not None:
            try:
                return json.dumps(decision["raw"], ensure_ascii=False)
            except Exception:
                pass
        return decision.get("summary") or fallback

    def _check_progress(self, streak: int) -> int:
        """
        单调性检测：基于"成功工具数量是否增加"判断是否仍有进展。
        每次工具调用后调用一次；若成功工具数量未增加，streak+1，否则重置为 0。
        """
        if not self.tool_results:
            return streak + 1
        if not hasattr(self, "_prev_success_count"):
            self._prev_success_count = 0
        success_count = sum(1 for r in self.tool_results if r.status == "success")
        if success_count > self._prev_success_count:
            self._prev_success_count = success_count
            return 0
        return streak + 1

    def _force_converge(self, reason: str = "连续无进展") -> AgentResult:
        """提前收敛：基于已有信息强制输出结论"""
        self._log_thinking(f"{reason}，基于已有结论收敛")
        logger.warning("[%s] %s，提前收敛", self.agent_name, reason)
        return self._force_finalize(reason)

    def _force_finalize(self, reason: str = "达到研究迭代上限") -> AgentResult:
        """
        强制收敛（迭代上限 / 连续无进展 / 连续无法解析时触发）：
        追加收敛指令，让模型基于已有工具结果输出最终结论。
        final_instruction 为空时按调研 Agent 的默认格式（FINAL:）要求输出；
        SummaryAgent 会传入 JSON 格式要求，避免产出缺少章节的文本。
        """
        if self.budget is not None and not self.budget.spend_llm():
            return AgentResult(
                agent_name=self.agent_name,
                conclusion="",
                evidence_refs=self._collect_evidence_refs(),
                tool_calls=self.tool_results,
                thinking_log=self.thinking_log,
                error="LLM 调用预算耗尽",
                degraded=True,
            )

        instruction = self.final_instruction or (
            "以 FINAL: 开头输出核心发现与判断，覆盖已获得的工具结果"
        )
        self.messages.append({
            "role": "user",
            "content": (
                f"已触发收敛（原因：{reason}）。请立即基于目前已有的全部工具结果输出最终结论，"
                f"不要再调用任何工具。格式要求：{instruction}"
            ),
        })
        started = time.time()
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            content = getattr(response.choices[0].message, "content", None) or ""
            self._obs_record_llm(started, "ok", content)
        except Exception as e:
            logger.warning("[%s] 强制收敛调用失败，回退日志拼接: %s", self.agent_name, e)
            try:
                from obs.store import classify_error

                self._obs_record_llm(started, classify_error(e), error=str(e))
            except Exception:
                pass
            content = ""

        if content.strip():
            decision = self._parse_decision(content)
            if decision["type"] == "final":
                return self._build_result(self._final_conclusion(decision, content))
            # 已要求"不要再调用工具"，若模型仍返回 tool 决策：
            # 不执行工具（避免浪费调用又丢弃结果），直接把文本作为结论
            return self._build_result(content)

        # 兜底：LLM 调用失败时返回简短收敛说明（不再拼接思考日志，
        # 避免前端 thinking_log 与 conclusion 重复展示）
        conclusion = f"{reason}，已基于已有工具结果收敛。请查看上方思考与工具记录。"
        if self.thinking_log:
            last_thought = self.thinking_log[-1]
            if last_thought and not last_thought.startswith("收敛"):
                conclusion = f"已收敛。最后思考：{last_thought}"
        return AgentResult(
            agent_name=self.agent_name,
            conclusion=conclusion,
            evidence_refs=self._collect_evidence_refs(),
            tool_calls=self.tool_results,
            thinking_log=self.thinking_log,
        )

    # ---------- Function Calling 路径 ----------

    @staticmethod
    def _is_unsupported_tools_error(exc: Exception) -> bool:
        """判断异常是否表示"模型/接口不支持 tools 参数"（而非网络抖动）"""
        name = type(exc).__name__
        if name in ("BadRequestError", "UnprocessableEntityError"):
            return True
        if isinstance(exc, TypeError):
            return True
        text = str(exc).lower()
        return any(k in text for k in ("unsupported", "does not support tools", "function calling", "invalid tools"))

    def _try_function_calling(self) -> Optional[str]:
        """
        尝试使用 function calling。
        - 模型本轮有工具调用：处理工具调用，返回 ""（表示已处理，继续循环）
        - 模型本轮直接给出文本回答（无 tool_calls）：返回文本内容
        - function calling 不可用：返回 None（降级文本协议）
        网络类异常重试 1 次；仅"不支持 tools"或重试后仍失败才永久降级。
        """
        if self.budget is not None and not self.budget.spend_llm():
            raise RuntimeError("LLM 调用预算耗尽")

        attempt = 0
        while True:
            started = time.time()
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=self.messages,
                    tools=self._tool_schemas_for_api(),
                    tool_choice="auto",
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
                self._tools_supported = True

                message = response.choices[0].message if response.choices else None
                tool_calls = getattr(message, "tool_calls", None) or []
                if tool_calls:
                    self._obs_record_llm(started, "ok", "")
                    self._handle_function_calls(tool_calls)
                    return ""  # 已处理工具调用，继续循环
                # 无工具调用：返回模型文本回答（交给上层解析）
                content = getattr(message, "content", None) or ""
                self._obs_record_llm(started, "ok", content)
                return content if content.strip() else None
            except Exception as e:
                if self._is_unsupported_tools_error(e):
                    self._tools_supported = False
                    events.agent_degraded(self.task_id, self.agent_name, str(e), permanent=True)
                    logger.warning("[%s] 模型不支持 function calling，降级文本协议: %s", self.agent_name, e)
                    return None
                attempt += 1
                if attempt <= 1:
                    logger.warning("[%s] function calling 调用异常，重试一次: %s", self.agent_name, e)
                    time.sleep(0.5)
                    continue
                self._tools_supported = False
                events.agent_degraded(self.task_id, self.agent_name, str(e), permanent=False)
                logger.warning("[%s] function calling 连续失败，降级文本协议: %s", self.agent_name, e)
                return None

    def _handle_function_calls(self, tool_calls) -> None:
        """处理 function calling 返回"""
        # 收集本轮所有工具调用（一次响应可能包含多个）
        prepared = []
        for call in tool_calls:
            fn = call.function
            try:
                args = json.loads(fn.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            prepared.append({
                "id": call.id,
                "name": fn.name,
                "args": args,
                "arguments_json": fn.arguments or "{}",
            })

        # 1. 合并为一条 assistant 消息声明全部 tool_calls（OpenAI 协议要求）
        if prepared:
            self.messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": p["id"],
                        "type": "function",
                        "function": {"name": p["name"], "arguments": p["arguments_json"]},
                    }
                    for p in prepared
                ],
            })

        # 2. 逐个执行工具，按 tool_call_id 回填 tool 消息（结果截断防膨胀）
        for p in prepared:
            result = self._execute_tool(p["name"], p["args"])
            self.messages.append({
                "role": "tool",
                "tool_call_id": p["id"],
                "content": self._serialize_result(result),
            })

    # ---------- 文本协议路径 ----------

    def _obs_record_llm(self, started: float, status: str, output: str = "", error: str = "") -> None:
        """记录一次分析师 ReAct 模型调用（失败不影响主流程）。"""
        try:
            import hashlib
            import json

            from obs.context import current
            from obs.store import classify_error, get_store

            ctx = current()
            task_id = ctx.get("task_id") or getattr(self, "task_id", "")
            if not task_id:
                return
            digest = hashlib.sha1(
                json.dumps(self.messages, ensure_ascii=False, default=str).encode()
            ).hexdigest()[:16]
            get_store().record_llm(
                task_id,
                ctx.get("stage", "") or "L1",
                self.agent_name,
                self.model,
                int((time.time() - started) * 1000),
                status,
                sum(len(str(m.get("content") or "")) for m in self.messages),
                len(output or ""),
                None,
                None,
                digest,
                error,
            )
        except Exception:
            pass

    def _call_plain(self) -> str:
        """无 tools 调用 LLM"""
        if self.budget is not None and not self.budget.spend_llm():
            raise RuntimeError("LLM 调用预算耗尽")
        started = time.time()
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            message = response.choices[0].message if response.choices else None
            content = getattr(message, "content", None) or ""
            self._obs_record_llm(started, "ok", content)
            return content
        except Exception as e:
            try:
                from obs.store import classify_error

                self._obs_record_llm(started, classify_error(e), error=str(e))
            except Exception:
                pass
            logger.exception("[%s] LLM 调用失败: %s", self.agent_name, e)
            raise

    def _parse_decision(self, content: str) -> Dict[str, Any]:
        """解析模型输出的决策（JSON 兜底）"""
        content = content.strip()

        # 尝试提取 JSON 块
        json_block = self._extract_json(content)
        if json_block:
            try:
                data = json.loads(json_block)
                decision_type = str(data.get("decision", "")).strip().lower()
                if decision_type in ("final", "final_answer", "done", "answer"):
                    return {
                        "type": "final",
                        "summary": str(data.get("summary") or data.get("answer") or content),
                        "raw": data,
                    }
                if decision_type in ("tool", "call_tool", "action"):
                    return {
                        "type": "tool",
                        "tool": str(data.get("tool") or data.get("tool_name") or ""),
                        "params": data.get("params") or data.get("arguments") or {},
                    }
            except json.JSONDecodeError:
                pass

        # 尝试 "TOOL:" / "FINAL:" 前缀协议
        tool_match = re.search(r"(?:TOOL|ACTION)\s*:\s*(\w+)\s*(?:\n|\|)?\s*(.*)", content, re.IGNORECASE | re.DOTALL)
        if tool_match:
            tool_name = tool_match.group(1).strip()
            params_text = tool_match.group(2).strip()
            params = {}
            try:
                params = json.loads(params_text) if params_text else {}
            except json.JSONDecodeError:
                params = {"raw": params_text}
            return {"type": "tool", "tool": tool_name, "params": params}

        if re.search(r"\bFINAL\s*(?:ANSWER)?\s*:", content, re.IGNORECASE):
            cleaned = re.sub(
                r"\bFINAL\s*(?:ANSWER)?\s*:", "", content, count=1, flags=re.IGNORECASE
            ).strip()
            return {"type": "final", "summary": cleaned or content}

        return {"type": "unknown"}

    @staticmethod
    def _extract_json(text: str) -> Optional[str]:
        """提取文本中的 JSON 对象（含截断修复）"""
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            return match.group(0)
        # 截断场景：JSON 未闭合（LLM 输出被 max_tokens 截断），尝试补齐
        start = text.find("{")
        if start == -1:
            return None
        fragment = text[start:]
        depth = fragment.count("{") - fragment.count("}")
        if depth > 0:
            candidate = fragment + "}" * depth
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                pass
        return None

    # ---------- 工具执行 ----------

    def _handle_tool_call(self, tool_name: str, params: Dict[str, Any]) -> None:
        """文本协议方式执行工具"""
        self.messages.append({
            "role": "assistant",
            "content": f"TOOL: {tool_name} {json.dumps(params, ensure_ascii=False)}",
        })
        result = self._execute_tool(tool_name, params)
        self.messages.append({
            "role": "user",
            "content": f"工具 {tool_name} 返回: {self._serialize_result(result)}",
        })

    def _execute_tool(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行工具并记录事件"""
        events.tool_started(self.task_id, self.agent_name, tool_name, params)
        try:
            result = self.execute_tool(tool_name, params)
            self.tool_results.append(result)
            if self.on_tool_result is not None:
                try:
                    refs = self.on_tool_result(tool_name, params, result)
                    for ref in refs or []:
                        if ref not in self._ledger_refs:
                            self._ledger_refs.append(ref)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("[%s] 证据登记回调失败: %s", self.agent_name, exc)
            if result.status == "failed":
                events.tool_failed(self.task_id, self.agent_name, tool_name, result.error or "未知错误")
            else:
                events.tool_completed(
                    self.task_id, self.agent_name, tool_name,
                    result.status, result.latency_ms,
                    summary=self._summarize_tool_result(result),
                )
            return result.model_dump()
        except Exception as e:
            logger.exception("[%s] 工具执行异常: %s", self.agent_name, tool_name)
            events.tool_failed(self.task_id, self.agent_name, tool_name, str(e))
            return {"tool_name": tool_name, "status": "failed", "error": str(e)}

    @staticmethod
    def _summarize_tool_result(result: ToolResult) -> str:
        """生成工具结果摘要（超长时截断并加省略号）"""
        if result.status == "failed":
            return result.error or "执行失败"
        data = result.data or {}
        summary = data.get("summary")
        if summary:
            text = str(summary)
            return text if len(text) <= 200 else text[:197] + "..."
        for key in ("items", "data", "results", "list"):
            if isinstance(data.get(key), list):
                return f"返回 {len(data[key])} 条数据"
        text = str(data)
        return text if len(text) <= 100 else text[:97] + "..."

    @staticmethod
    def _serialize_result(result: Dict[str, Any]) -> str:
        """
        序列化工具结果回填给模型。
        超长时按结构压缩（长字符串截断、长数组保留前 N 条），保证回填内容始终是合法 JSON。
        """
        for max_str, max_items in _COMPACT_LEVELS:
            text = json.dumps(
                ReActLoop._compact_value(result, max_str, max_items),
                ensure_ascii=False,
                default=str,
            )
            if len(text) <= MAX_TOOL_RESULT_CHARS:
                return text
        # 极端情况（层级极深/键极多）：退回硬截断并明确标注，避免回填非法 JSON
        compacted = json.dumps(
            ReActLoop._compact_value(result, 80, 2),
            ensure_ascii=False,
            default=str,
        )
        if len(compacted) <= MAX_TOOL_RESULT_CHARS:
            return compacted
        return json.dumps({
            "tool_name": result.get("tool_name", ""),
            "status": result.get("status", ""),
            "note": f"结果过长（{len(compacted)} 字符），已省略明细",
        }, ensure_ascii=False)

    @staticmethod
    def _compact_value(value: Any, max_str: int, max_items: int) -> Any:
        """递归压缩结构：长字符串截断、长数组保留前 N 条"""
        if isinstance(value, str):
            return value if len(value) <= max_str else value[:max_str] + "…(截断)"
        if isinstance(value, list):
            head = [ReActLoop._compact_value(v, max_str, max_items) for v in value[:max_items]]
            if len(value) > max_items:
                head.append(f"…(共 {len(value)} 条，仅保留前 {max_items} 条)")
            return head
        if isinstance(value, dict):
            return {k: ReActLoop._compact_value(v, max_str, max_items) for k, v in value.items()}
        return value

    # ---------- 辅助 ----------

    def _log_thinking(self, thought: str) -> None:
        if self.emit_thinking:
            events.agent_thinking(self.task_id, self.agent_name, thought)
        self.thinking_log.append(thought)

    def _collect_evidence_refs(self) -> List[str]:
        """优先返回证据台账 ID；无台账时回退为工具调用序号"""
        if self._ledger_refs:
            return list(self._ledger_refs)
        refs: List[str] = []
        for idx, tr in enumerate(self.tool_results):
            if tr.status != "success":
                continue
            ref = f"{tr.tool_name}:{tr.step_id or idx + 1}"
            if ref not in refs:
                refs.append(ref)
        return refs
