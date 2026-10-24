#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
回测指标（纯函数）

主指标是校准与增量，不是收益率：
- hit / alpha：方向能力
- Brier：置信度校准
- calibration：分桶命中率
- debate_lift：有/无辩论的差值
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional


def is_hit(stance: str, future_return: float, neutral_band: float = 0.03) -> bool:
    """方向命中：neutral 定义为绝对收益小于阈值"""
    stance = str(stance or "neutral").lower()
    if stance == "bullish":
        return future_return > 0
    if stance == "bearish":
        return future_return < 0
    return abs(future_return) <= neutral_band


def compute_alpha(stock_return: float, benchmark_return: Optional[float]) -> Optional[float]:
    if benchmark_return is None:
        return None
    return stock_return - benchmark_return


def brier_score(conviction: float, hit: bool) -> float:
    """Brier score（越低越好）：(置信度 - 实际命中)^2"""
    target = 1.0 if hit else 0.0
    return (float(conviction) - target) ** 2


def calibration_table(records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    置信度分桶命中率。records 需含 conviction / hit。
    """
    buckets = [
        (0.0, 0.4, "0.0-0.4"),
        (0.4, 0.6, "0.4-0.6"),
        (0.6, 0.8, "0.6-0.8"),
        (0.8, 1.01, "0.8-1.0"),
    ]
    rows = [r for r in records if r.get("hit") is not None]
    output = []
    for low, high, label in buckets:
        subset = [r for r in rows if low <= float(r.get("conviction") or 0) < high]
        hits = sum(1 for r in subset if r["hit"])
        output.append({
            "bucket": label,
            "samples": len(subset),
            "hit_rate": round(hits / len(subset), 3) if subset else None,
            "avg_conviction": round(
                sum(float(r.get("conviction") or 0) for r in subset) / len(subset), 3
            ) if subset else None,
        })
    return output


def summarize(records: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """
    汇总回测结果。

    records 字段：stance, conviction, ret, benchmark_ret, debate_enabled, unstable
    """
    all_records = list(records)
    rows = [r for r in all_records if r.get("hit") is not None and not r.get("unstable")]
    unstable = sum(1 for r in all_records if r.get("unstable"))
    total = len(all_records)

    if not rows:
        return {
            "total": total,
            "settled": 0,
            "unstable": unstable,
            "hit_rate": None,
            "avg_return": None,
            "avg_alpha": None,
            "brier": None,
            "calibration": calibration_table([]),
            "by_stance": {},
            "debate_lift": None,
        }

    hits = sum(1 for r in rows if r["hit"])
    alphas = [r["alpha"] for r in rows if r.get("alpha") is not None]
    returns = [float(r["ret"]) for r in rows if r.get("ret") is not None]
    briers = [brier_score(r.get("conviction", 0.5), r["hit"]) for r in rows]

    by_stance: Dict[str, Dict[str, Any]] = {}
    for stance in ("bullish", "neutral", "bearish"):
        subset = [r for r in rows if str(r.get("stance")) == stance]
        if subset:
            by_stance[stance] = {
                "samples": len(subset),
                "hit_rate": round(sum(1 for r in subset if r["hit"]) / len(subset), 3),
                "avg_return": round(
                    sum(float(r.get("ret") or 0) for r in subset) / len(subset), 4
                ),
            }

    debate_lift = None
    with_debate = [r for r in rows if r.get("debate_enabled") is True]
    without = [r for r in rows if r.get("debate_enabled") is False]
    if with_debate and without:
        rate_with = sum(1 for r in with_debate if r["hit"]) / len(with_debate)
        rate_without = sum(1 for r in without if r["hit"]) / len(without)
        debate_lift = round(rate_with - rate_without, 3)

    return {
        "total": total,
        "settled": len(rows),
        "unstable": unstable,
        "hit_rate": round(hits / len(rows), 3),
        "avg_return": round(sum(returns) / len(returns), 4) if returns else None,
        "avg_alpha": round(sum(alphas) / len(alphas), 4) if alphas else None,
        "brier": round(sum(briers) / len(briers), 4),
        "calibration": calibration_table(rows),
        "by_stance": by_stance,
        "debate_lift": debate_lift,
    }


def majority_stance(stances: List[str]) -> str:
    """多次运行的多数方向（用于非确定性处理）"""
    counts: Dict[str, int] = {}
    for stance in stances:
        counts[stance] = counts.get(stance, 0) + 1
    if not counts:
        return "neutral"
    return max(counts.items(), key=lambda item: item[1])[0]


def is_unstable(stances: List[str]) -> bool:
    """3 次运行中至少 2 种方向 → 不稳定"""
    return len(set(stances)) > 1
