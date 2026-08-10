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
from typing import Any, Dict, List, Optional

from openai import OpenAI

from agents import events
from agents.state import AgentResult, ToolResult

logger = logging.getLogger(__name__)

# 单条工具结果回填给模型的最大字符数（防止多轮后上下文膨胀）
MAX_TOOL_RESULT_CHARS = 3000


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
        shared_pool: Optional["SharedFindingsPool"] = None,
        max_tokens: int = 8192,
        keep_full_json: bool = False,
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
        self.shared_pool = shared_pool  # 共享发现池（可为 None，单 Agent 场景）
        self._pool_cursor = 0  # 已注入到本循环的池游标
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

        for step in range(self.max_iterations):
            # 注入共享发现池中的新发现（供本轮决策参考）
            self._inject_shared_findings()

            # 带工具调用尝试（仅在首次或确认支持后）
            if self._tools_supported is not False:
                text_answer = self._try_function_calling()
                if text_answer is not None and text_answer != "":
                    # 模型本轮未调用工具，直接给出了文本回答
                    content = text_answer.strip()
                    self._publish_findings(content)
                    decision = self._parse_decision(content)
                    if decision["type"] == "final":
                        self._log_thinking("收敛: 已完成调研，整理输出研究结论")
                        return self._build_result(self._final_conclusion(decision, content))
                    if decision["type"] == "tool":
                        self._handle_tool_call(decision.get("tool", ""), decision.get("params", {}))
                        no_progress_streak = self._check_progress(no_progress_streak)
                        if no_progress_streak >= 2:
                            return self._force_converge()
                        continue
                    # 无法解析：作为思考记录，继续循环
                    self._log_thinking(content)
                    self.messages.append({"role": "assistant", "content": content})
                    continue
                if text_answer == "":
                    # 已处理工具调用，继续循环
                    no_progress_streak = self._check_progress(no_progress_streak)
                    if no_progress_streak >= 2:
                        return self._force_converge()
                    continue

            # 文本协议路径（function calling 不可用）
            response = self._call_plain()
            content = response or ""
            self._publish_findings(content)
            decision = self._parse_decision(content)

            if decision["type"] == "final":
                self._log_thinking("收敛: 已完成调研，整理输出研究结论")
                return self._build_result(self._final_conclusion(decision, content))

            if decision["type"] == "tool":
                self._handle_tool_call(decision.get("tool", ""), decision.get("params", {}))
                continue

            # 无法解析：把内容作为思考记录，继续循环
            self._log_thinking(content)
            self.messages.append({"role": "assistant", "content": content})

        # 达到上限：强制收敛（让模型基于已有数据综合输出，而非直接拼接日志）
        logger.warning("[%s] 达到最大迭代 %d 次，触发强制收敛", self.agent_name, self.max_iterations)
        return self._force_finalize()

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

    def _force_converge(self) -> AgentResult:
        """连续无进展：基于已有信息强制收敛"""
        self._log_thinking("工具连续无新增信息，基于已有结论收敛")
        logger.warning("[%s] 工具连续无进展，提前收敛", self.agent_name)
        return self._force_finalize()

    def _force_finalize(self) -> AgentResult:
        """
        强制收敛（迭代上限 / 连续无进展时触发）：
        追加收敛指令，让模型基于已有工具结果输出最终结论。
        相比直接拼接 thinking_log，可产出结构化、可用的结论。
        """
        self.messages.append({
            "role": "user",
            "content": (
                "已到达研究迭代上限，请立即基于目前已有的全部工具结果，"
                "输出最终结论（以 FINAL: 开头，覆盖核心发现与判断即可，不要再调用任何工具）。"
            ),
        })
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            content = getattr(response.choices[0].message, "content", None) or ""
        except Exception as e:
            logger.warning("[%s] 强制收敛调用失败，回退日志拼接: %s", self.agent_name, e)
            content = ""

        if content.strip():
            decision = self._parse_decision(content)
            if decision["type"] == "final":
                return self._build_result(self._final_conclusion(decision, content))
            if decision["type"] == "tool":
                self._handle_tool_call(decision.get("tool", ""), decision.get("params", {}))
            return self._build_result(content)

        # 兜底：LLM 调用失败时返回简短收敛说明（不再拼接思考日志，
        # 避免前端 thinking_log 与 conclusion 重复展示）
        conclusion = "分析达到迭代上限，基于已有工具结果收敛。请查看上方思考与工具记录。"
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

    def _try_function_calling(self) -> Optional[str]:
        """
        尝试使用 function calling。
        - 模型本轮有工具调用：处理工具调用，返回 ""（表示已处理，继续循环）
        - 模型本轮直接给出文本回答（无 tool_calls）：返回文本内容
        - function calling 不可用：返回 None（降级文本协议）
        """
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
                self._handle_function_calls(tool_calls)
                return ""  # 已处理工具调用，继续循环
            # 无工具调用：返回模型文本回答（交给上层解析）
            content = getattr(message, "content", None) or ""
            return content if content.strip() else None
        except Exception as e:
            logger.warning("[%s] function calling 不可用，降级文本协议: %s", self.agent_name, e)
            self._tools_supported = False
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

    def _call_plain(self) -> str:
        """无 tools 调用 LLM"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            message = response.choices[0].message if response.choices else None
            return getattr(message, "content", None) or ""
        except Exception as e:
            logger.exception("[%s] LLM 调用失败: %s", self.agent_name, e)
            return f'{{"decision": "final", "summary": "模型调用失败: {e}"}}'

    # ---------- 共享发现池（P0 信息共享） ----------

    def _inject_shared_findings(self) -> None:
        """
        每轮决策前，将共享池中自上次读取以来的新发现注入对话上下文。
        通过 system message 尾部追加（不影响既有消息结构）。
        """
        if self.shared_pool is None:
            return
        try:
            new_findings = self.shared_pool.get_since(self._pool_cursor)
            if not new_findings:
                return
            self._pool_cursor += len(new_findings)
            from agents.shared_pool import SharedFindingsPool

            block = SharedFindingsPool.format_findings(new_findings)
            if block:
                self.messages.append({"role": "system", "content": block})
        except Exception as exc:
            logger.warning("[%s] 注入共享发现失败: %s", self.agent_name, exc)

    def _publish_findings(self, content: str) -> None:
        """
        从模型输出中解析 [FINDINGS] 广播并写入共享池。
        约定：模型在文本回答中以 "[FINDINGS] 文本" 或 "FINDINGS: 文本" 前缀输出发现。
        """
        if self.shared_pool is None:
            return
        if not content:
            return
        try:
            pattern = re.compile(r"(?:\[FINDINGS\]|FINDINGS\s*:)\s*(.+)", re.IGNORECASE)
            for match in pattern.finditer(content):
                finding = match.group(1).strip()
                if finding:
                    self.shared_pool.publish(self.agent_name, finding)
        except Exception as exc:
            logger.warning("[%s] 广播发现失败: %s", self.agent_name, exc)

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
        """序列化工具结果回填给模型，超长时截断防止上下文膨胀"""
        text = json.dumps(result, ensure_ascii=False, default=str)
        if len(text) > MAX_TOOL_RESULT_CHARS:
            return text[:MAX_TOOL_RESULT_CHARS] + "……(结果过长已截断)"
        return text

    # ---------- 辅助 ----------

    def _log_thinking(self, thought: str) -> None:
        if self.emit_thinking:
            events.agent_thinking(self.task_id, self.agent_name, thought)
        self.thinking_log.append(thought)

    def _collect_evidence_refs(self) -> List[str]:
        """从工具结果收集证据引用"""
        refs = []
        for tr in self.tool_results:
            if tr.status == "success" and tr.asset_id:
                refs.append(tr.asset_id)
            elif tr.status == "success":
                refs.append(tr.tool_name)
        return refs
