#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
预算与追踪

Budget：全链路共享的硬约束（LLM 调用数 / 工具调用数 / 修复次数）。
Trace：每次任务的阶段耗时、调用量、降级原因，写入任务结果与 SQLite。
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional


class Budget:
    """线程安全预算计数器"""

    def __init__(
        self,
        llm_calls: int = 20,
        tool_calls: int = 24,
        repair_calls: int = 2,
    ):
        self._lock = threading.Lock()
        self.llm_calls = int(llm_calls)
        self.tool_calls = int(tool_calls)
        self.repair_calls = int(repair_calls)
        self.used_llm = 0
        self.used_tool = 0
        self.used_repair = 0

    def spend_llm(self, n: int = 1) -> bool:
        with self._lock:
            if self.used_llm + n > self.llm_calls:
                return False
            self.used_llm += n
            return True

    def spend_tool(self, n: int = 1) -> bool:
        with self._lock:
            if self.used_tool + n > self.tool_calls:
                return False
            self.used_tool += n
            return True

    def spend_repair(self) -> bool:
        with self._lock:
            if self.used_repair >= self.repair_calls:
                return False
            self.used_repair += 1
            return True

    def exhausted(self) -> bool:
        with self._lock:
            return self.used_llm >= self.llm_calls

    def snapshot(self) -> Dict[str, int]:
        with self._lock:
            return {
                "llm_calls": self.llm_calls,
                "llm_used": self.used_llm,
                "tool_calls": self.tool_calls,
                "tool_used": self.used_tool,
                "repair_calls": self.repair_calls,
                "repair_used": self.used_repair,
            }

    @classmethod
    def from_plan(cls, plan: Any, max_llm: int = 40, max_tool: int = 50) -> "Budget":
        """按计划分配预算，并受硬上限约束"""
        return cls(
            llm_calls=min(int(getattr(plan, "llm_calls", 32) or 32), max_llm),
            tool_calls=min(int(getattr(plan, "tool_calls", 36) or 36), max_tool),
        )


class Trace:
    """任务阶段追踪"""

    def __init__(self):
        self.started_at = time.time()
        self.phases: List[Dict[str, Any]] = []
        self.notes: List[str] = []

    def add_phase(
        self,
        name: str,
        duration_ms: int,
        degraded: bool = False,
        detail: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.phases.append({
            "phase": name,
            "duration_ms": int(duration_ms),
            "degraded": bool(degraded),
            "detail": detail or {},
        })

    def note(self, text: str) -> None:
        self.notes.append(str(text))

    def measure(self, name: str) -> "_PhaseTimer":
        return _PhaseTimer(self, name)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_ms": int((time.time() - self.started_at) * 1000),
            "phases": list(self.phases),
            "notes": list(self.notes),
        }

    def slowest_phase(self) -> Optional[Dict[str, Any]]:
        if not self.phases:
            return None
        return max(self.phases, key=lambda p: p.get("duration_ms", 0))


class _PhaseTimer:
    """with trace.measure("L1") as timer: ..."""

    def __init__(self, trace: Trace, name: str):
        self.trace = trace
        self.name = name
        self.degraded = False
        self.detail: Dict[str, Any] = {}
        self._t0 = 0.0

    def __enter__(self) -> "_PhaseTimer":
        self._t0 = time.time()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.trace.add_phase(
            self.name,
            int((time.time() - self._t0) * 1000),
            degraded=self.degraded or exc_type is not None,
            detail=self.detail,
        )
        return False
