#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""回测报告"""

from __future__ import annotations

import json
from typing import Any, Dict, List


def render(result: Dict[str, Any]) -> str:
    summary = result.get("summary") or {}
    lines = [
        f"回测 run_id: {result.get('run_id')}",
        f"样本: {summary.get('settled')} / {summary.get('total')}"
        f"（不稳定 {summary.get('unstable', 0)}）",
        f"方向命中率: {_pct(summary.get('hit_rate'))}",
        f"平均收益: {_pct(summary.get('avg_return'))}",
        f"平均超额: {_pct(summary.get('avg_alpha'))}",
        f"Brier: {summary.get('brier')}",
        f"辩论增量: {_pct(summary.get('debate_lift'))}",
    ]
    if result.get("universe_bias"):
        lines.append("⚠ 未取到历史成分股，本批样本不进入统计汇总")
    calibration = summary.get("calibration") or []
    if calibration:
        lines.append("置信度校准:")
        for row in calibration:
            lines.append(
                f"  {row.get('bucket')}: n={row.get('samples')} "
                f"命中={_pct(row.get('hit_rate'))} 平均置信度={row.get('avg_conviction')}"
            )
    return "\n".join(lines)


def to_json(result: Dict[str, Any]) -> str:
    return json.dumps(result, ensure_ascii=False, indent=2, default=str)


def _pct(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return str(value)
