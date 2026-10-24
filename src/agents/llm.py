#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
结构化 LLM 调用封装

与 ReActLoop 的区别：本模块面向"一次调用、结构化输出"的场景
（Supervisor 计划、论点、辩论、裁决、质检），不涉及工具循环。

职责：
1. 统一超时与重试（1 次）
2. 统一 JSON 提取与截断修复
3. 统一预算扣减
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from openai import OpenAI

from agents.budget import Budget
from utils.llm_common import build_client, get_env

logger = logging.getLogger(__name__)


class BudgetExceeded(RuntimeError):
    """LLM 调用预算耗尽"""


class LLM:
    """结构化 LLM 客户端"""

    def __init__(
        self,
        model: Optional[str] = None,
        timeout: float = 90.0,
        temperature: float = 0.2,
        budget: Optional[Budget] = None,
        cache: Optional[Any] = None,
        task_id: str = "",
    ):
        self.model = model or get_env("AGENT_LLM_MODEL", "deepseek-chat")
        self.timeout = timeout
        self.temperature = temperature
        self.budget = budget
        self.cache = cache  # 可选：需提供 get(key)/set(key, value)
        self.task_id = task_id
        self._client: Optional[OpenAI] = None

    def _get_client(self) -> OpenAI:
        if self._client is None:
            self._client = build_client(timeout=self.timeout, max_retries=0)
        return self._client

    # ---------- 基础调用 ----------

    def chat(
        self,
        messages: List[Dict[str, Any]],
        max_tokens: int = 4096,
        json_mode: bool = False,
        temperature: Optional[float] = None,
    ) -> str:
        """单次调用，失败重试 1 次（支持响应缓存，用于回测重跑）"""
        import hashlib as _hashlib
        import time as _time

        started = _time.time()
        task_id = stage = agent = ""
        try:
            from obs.context import current as _obs_current

            _ctx = _obs_current()
            task_id, stage, agent = (
                getattr(self, "task_id", "") or _ctx.get("task_id", ""),
                _ctx.get("stage", ""),
                _ctx.get("agent", ""),
            )
        except Exception:
            pass
        try:
            from obs.store import classify_error as _classify_error
        except Exception:
            def _classify_error(_value):
                return "internal"
        prompt_chars = sum(len(str(m.get("content") or "")) for m in messages)
        prompt_hash = _hashlib.sha1(
            json.dumps(messages, ensure_ascii=False, default=str).encode()
        ).hexdigest()[:16]

        def _record(status, error="", output_chars=0, prompt_tokens=None, completion_tokens=None):
            if not task_id:
                return
            try:
                from obs.store import get_store as _get_store

                _get_store().record_llm(
                    task_id, stage, agent, self.model,
                    int((_time.time() - started) * 1000), status,
                    prompt_chars, output_chars, prompt_tokens, completion_tokens,
                    prompt_hash, error,
                )
            except Exception:
                pass

        cache_key = None
        if self.cache is not None:
            cache_key = _cache_key(
                self.model, messages,
                self.temperature if temperature is None else temperature,
                max_tokens, json_mode,
            )
            try:
                cached = self.cache.get(cache_key)
                if cached:
                    _record("cache", output_chars=len(cached))
                    return cached
            except Exception as exc:  # noqa: BLE001
                logger.warning("LLM 缓存读取失败: %s", exc)

        if self.budget is not None and not self.budget.spend_llm():
            raise BudgetExceeded("LLM 调用预算已耗尽")

        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature if temperature is None else temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        last_error: Optional[Exception] = None
        for attempt in range(3):
            try:
                response = self._get_client().chat.completions.create(**kwargs)
                if not response.choices:
                    _record("ok", output_chars=0)
                    return ""
                content = getattr(response.choices[0].message, "content", None) or ""
                if cache_key and self.cache is not None:
                    try:
                        self.cache.set(cache_key, content)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("LLM 缓存写入失败: %s", exc)
                _usage = getattr(response, "usage", None)
                _record(
                    "ok",
                    output_chars=len(content),
                    prompt_tokens=getattr(_usage, "prompt_tokens", None) if _usage else None,
                    completion_tokens=getattr(_usage, "completion_tokens", None) if _usage else None,
                )
                return content
            except Exception as exc:  # noqa: BLE001  (需要按错误类型决定是否降级)
                last_error = exc
                if json_mode and _is_format_unsupported(exc):
                    kwargs.pop("response_format", None)
                    continue
                if _is_timeout(exc):
                    logger.warning("LLM 调用超时，不再重试: %s", exc)
                    break
                if _is_upstream_error(exc) and attempt < 2:
                    logger.warning("LLM 上游 5xx，退避后重试: %s", exc)
                    _time.sleep(0.5 * (attempt + 1))
                    continue
                if attempt == 0:
                    logger.warning("LLM 调用失败，重试一次: %s", exc)
                    continue
                break
        logger.error("LLM 调用失败: %s", last_error)
        _record(_classify_error(last_error), error=str(last_error))
        raise RuntimeError(f"LLM 调用失败: {last_error}")

    def text(self, system: str, user: str, max_tokens: int = 2048) -> str:
        """纯文本输出"""
        return self.chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            max_tokens=max_tokens,
        )

    def json(
        self,
        system: str,
        user: str,
        max_tokens: int = 4096,
        required_keys: Optional[List[str]] = None,
        temperature: Optional[float] = None,
        retries: int = 1,
    ) -> Optional[Dict[str, Any]]:
        """
        结构化 JSON 输出。解析失败时追加一次"只输出 JSON"的纠正重试。

        Returns:
            解析成功的 dict；两次都失败返回 None
        """
        messages = [
            {"role": "system", "content": system + "\n\n只输出一个 JSON 对象，不要推理过程、不要代码块、不要解释。"},
            {"role": "user", "content": f"只输出 JSON（第一个字符必须是 {{）。\n\n{user}"},
        ]
        content = self.chat(messages, max_tokens=max_tokens, json_mode=True, temperature=temperature)
        data = _pick_json(content, required_keys)
        if data is not None:
            return data

        if retries <= 0:
            logger.warning("LLM JSON 解析失败（不重试），原始输出前 300 字: %s", (content or "")[:300])
            return None

        # 不把上一次的错误输出放回上下文，避免模型延续错误话题
        messages.append({
            "role": "user",
            "content": "上一次输出不是合法 JSON 或缺少必需字段。请严格按上面的要求重新输出一个 JSON 对象，不要延续其他话题。",
        })
        try:
            content = self.chat(messages, max_tokens=max_tokens, json_mode=True, temperature=0)
        except RuntimeError:
            return None
        data = _pick_json(content, required_keys)
        if data is not None:
            return data
        logger.warning("LLM JSON 解析失败，原始输出前 300 字: %s", (content or "")[:300])
        return None


# ---------- JSON 提取 ----------

def _pick_json(text: Optional[str], required_keys: Optional[List[str]]) -> Optional[Dict[str, Any]]:
    """从模型输出中挑选第一个满足必需字段的 JSON 对象（容忍前置推理文本）"""
    candidates = extract_json_objects(text)
    for data in candidates:
        if _has_keys(data, required_keys):
            return data
    return None


def extract_json_objects(text: Optional[str]) -> List[Dict[str, Any]]:
    """扫描文本中所有可解析的 JSON 对象（推理模型常先输出思考再给 JSON）"""
    if not text:
        return []
    raw = text.strip()
    fence = _FENCE_RE.search(raw)
    if fence:
        raw = fence.group(1).strip()

    decoder = json.JSONDecoder()
    results: List[Dict[str, Any]] = []
    for index, char in enumerate(raw):
        if char != "{":
            continue
        try:
            data, _ = decoder.raw_decode(raw[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            results.append(data)
        if len(results) >= 20:
            break

    if results:
        return results
    # 截断修复兜底：对所有 `{` 起点依次尝试（优先靠后的，答案通常在后半段）
    positions = [i for i, ch in enumerate(raw) if ch == "{"][:20]
    repaired_objects: List[Dict[str, Any]] = []
    for index in positions:
        repaired = _repair_brackets(raw[index:])
        if not repaired:
            continue
        try:
            data = json.loads(repaired)
            if isinstance(data, dict):
                repaired_objects.append(data)
        except json.JSONDecodeError:
            continue
    # 外层对象字段更多，优先返回
    repaired_objects.sort(key=len, reverse=True)
    return repaired_objects


def _cache_key(
    model: str,
    messages: List[Dict[str, Any]],
    temperature: float,
    max_tokens: int,
    json_mode: bool,
) -> str:
    """按模型 + 完整输入生成缓存键"""
    import hashlib

    raw = json.dumps(
        {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "json_mode": json_mode,
        },
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def _is_upstream_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(key in text for key in ("502", "503", "504", "upstream", "service unavailable"))


def _is_timeout(exc: Exception) -> bool:
    text = str(exc).lower()
    return isinstance(exc, TimeoutError) or "timed out" in text or "timeout" in text


def extract_json_object(text: Optional[str]) -> Optional[Dict[str, Any]]:
    """从任意文本中提取第一个可解析的 JSON 对象"""
    if not text:
        return None
    raw = text.strip()

    fence = _FENCE_RE.search(raw)
    if fence:
        raw = fence.group(1).strip()

    objects = extract_json_objects(raw)
    return objects[0] if objects else None


def _repair_brackets(fragment: str) -> Optional[str]:
    """
    补齐未闭合的字符串与括号（按栈补对应的 } 或 ]）。
    只用于处理 LLM 输出被 max_tokens 截断的常见情况。
    """
    stack: List[str] = []
    in_string = False
    escape = False
    for char in fragment:
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            stack.append("}")
        elif char == "[":
            stack.append("]")
        elif char in "}]":
            if stack:
                stack.pop()

    candidate = fragment
    if in_string:
        candidate += '"'
    if stack:
        candidate += "".join(reversed(stack))
    return candidate if candidate != fragment else None


def _has_keys(data: Dict[str, Any], required_keys: Optional[List[str]]) -> bool:
    if not required_keys:
        return True
    return all(key in data for key in required_keys)


def _is_format_unsupported(exc: Exception) -> bool:
    """判断异常是否为"接口不支持 response_format" """
    name = type(exc).__name__
    if name in ("BadRequestError", "UnprocessableEntityError"):
        return True
    text = str(exc).lower()
    return any(k in text for k in ("response_format", "json_object", "unsupported", "invalid parameter"))
