#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
跨任务反思检索

不走向量检索：按资产/行业做结构化过滤，读取最近的决策反思。
"""

from __future__ import annotations

from typing import Any, Iterable, List, Optional

from memory import decision_store


def get_reflections(assets: Iterable[Any], limit: int = 8) -> str:
    """
    返回供 prompt 注入的反思文本。

    Args:
        assets: Asset 列表（取其 symbol/asset_id）
        limit: 最多注入条数
    """
    symbols: List[str] = []
    for asset in assets or []:
        symbol = getattr(asset, "symbol", None) or getattr(asset, "asset_id", None)
        if symbol:
            symbols.append(str(symbol))

    records = decision_store.list_recent(asset_id=symbols[0] if symbols else None, limit=limit * 2)
    if not symbols:
        records = decision_store.list_recent(limit=limit)

    lines: List[str] = []
    for record in records:
        reflection = record.get("reflection")
        if not reflection:
            continue
        settlement = record.get("settlement") or {}
        if not settlement:
            continue
        lines.append(f"- {reflection}")
        if len(lines) >= limit:
            break
    return "\n".join(lines)


def stats() -> dict:
    """粗略统计（供前端/调试）"""
    records = decision_store.list_recent(limit=200)
    settled = [r for r in records if r.get("settlement")]
    hits = [r for r in settled if (r.get("settlement") or {}).get("hit")]
    return {
        "total": len(records),
        "settled": len(settled),
        "hit_rate": round(len(hits) / len(settled), 3) if settled else None,
    }
