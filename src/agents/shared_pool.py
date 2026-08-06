#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
共享发现池（SharedFindingsPool）

多 Agent 并行调研时的信息共享中枢：
- 调研 Agent 在工具调用后提炼关键发现并广播入池
- 其他 Agent 每轮决策前增量读取池中最新发现，调整调研方向
- 第一轮结束后由 Orchestrator 汇总完整池，供第二轮补充调研使用

设计原则（2026-08-06 定稿）：
- 发现做相似去重，不做严格数量限制（给 Agent 充分空间）
- 增量读取（get_since），避免同一发现重复注入
- 线程安全，支持并行 Agent 同时读写
"""

from __future__ import annotations

import threading
import time
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional


class SharedFindingsPool:
    """共享发现池（线程安全）"""

    def __init__(self, dedup_threshold: float = 0.88):
        """
        Args:
            dedup_threshold: 相似度阈值，两条发现相似度 ≥ 此值视为重复（不写入）
        """
        self._lock = threading.Lock()
        self._findings: List[Dict[str, Any]] = []  # [{agent, text, ts}]
        self._dedup_threshold = dedup_threshold

    # ---------- 写入 ----------

    def publish(self, agent: str, text: str) -> bool:
        """
        广播一条发现。相似内容去重后写入。

        Returns:
            True 已写入；False 因重复被丢弃
        """
        text = (text or "").strip()
        if not text or len(text) < 5:
            return False
        with self._lock:
            for existing in self._findings:
                if self._similar(text, str(existing.get("text", ""))) >= self._dedup_threshold:
                    return False
            self._findings.append({
                "agent": agent,
                "text": text,
                "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            })
            return True

    @staticmethod
    def _similar(a: str, b: str) -> float:
        """文本相似度（SequenceMatcher）"""
        return SequenceMatcher(None, a, b).ratio()

    # ---------- 读取 ----------

    def get_since(self, cursor: int) -> List[Dict[str, Any]]:
        """返回游标之后的新发现（增量读取）"""
        with self._lock:
            return list(self._findings[cursor:])

    def get_all(self) -> List[Dict[str, Any]]:
        """返回全部发现（完整池）"""
        with self._lock:
            return list(self._findings)

    def __len__(self) -> int:
        with self._lock:
            return len(self._findings)

    def reset(self) -> None:
        """清空池（单次任务结束后调用）"""
        with self._lock:
            self._findings.clear()

    # ---------- 格式化 ----------

    @staticmethod
    def format_findings(findings: List[Dict[str, Any]], max_show: Optional[int] = None) -> str:
        """
        将发现列表格式化为可注入的文本块。

        Args:
            findings: 发现列表 [{agent, text, ts}]
            max_show: 最多展示条数（None 不限制）

        Returns:
            格式化文本（供注入 user message）
        """
        items = findings if max_show is None else findings[-max_show:]
        if not items:
            return ""
        lines = ["【其他研究员共享发现，供参考】"]
        for item in items:
            agent = str(item.get("agent", ""))
            text = str(item.get("text", ""))
            if agent:
                lines.append(f"[{agent}] {text}")
            else:
                lines.append(text)
        lines.append("如与你当前研究目标相关，可考虑据此调整后续工具调用方向或核实；不相关则忽略。")
        return "\n".join(lines)
