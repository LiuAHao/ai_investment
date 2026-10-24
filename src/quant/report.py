#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""量化回测报告"""

from __future__ import annotations

import json
from typing import Any, Dict

from quant.engine import QuantResult


def _pct(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value) * 100:.2f}%"
    except (TypeError, ValueError):
        return str(value)


def _num(value: Any, digits: int = 2) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def render(result: QuantResult) -> str:
    m = result.metrics
    lines = [
        f"标的: {result.symbol} | 策略: {result.strategy} | 参数: {result.params}",
        f"期末资产: {_num(m.get('final_equity'))}",
        "",
        f"总收益: {_pct(m.get('total_return'))} | 年化: {_pct(m.get('annual_return'))}",
        f"最大回撤: {_pct(m.get('max_drawdown'))} | 夏普: {_num(m.get('sharpe'))}",
        f"胜率: {_pct(m.get('win_rate'))} | 盈亏比: {_num(m.get('profit_factor'))} | 交易: {m.get('trades')} 笔",
        f"换手: {_num(m.get('turnover'))}x",
    ]
    if m.get("benchmark_return") is not None:
        lines.append(
            f"基准收益: {_pct(m.get('benchmark_return'))} | 超额: {_pct(m.get('alpha'))}"
        )
    if not m.get("trades"):
        lines.append(
            "⚠ 未产生任何交易：可能是初始资金不足一手，或策略信号始终为空。"
            "可用 --cash 调高资金，或检查 --params。"
        )
    return "\n".join(lines)


def to_json(result: QuantResult, include_trades: bool = False) -> str:
    payload: Dict[str, Any] = {
        "symbol": result.symbol,
        "strategy": result.strategy,
        "params": result.params,
        "metrics": result.metrics,
        "equity": [
            {"date": str(index.date()), "value": round(float(value), 2)}
            for index, value in result.equity.items()
        ],
    }
    if include_trades:
        payload["trades"] = result.trades
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def render_trades(result: QuantResult, limit: int = 0) -> str:
    rows = result.trades if limit <= 0 else result.trades[:limit]
    lines = ["日期       方向   价格      股数     金额      费用     盈亏"]
    for trade in rows:
        lines.append(
            f"{trade.get('date'):<10} {trade.get('side'):<5} "
            f"{trade.get('price'):<9} {trade.get('shares'):<8} "
            f"{trade.get('amount'):<9} {trade.get('fee'):<8} "
            f"{trade.get('pnl') if trade.get('pnl') is not None else '-'}"
        )
    if limit > 0 and len(result.trades) > limit:
        lines.append(f"... 其余 {len(result.trades) - limit} 笔")
    return "\n".join(lines)
