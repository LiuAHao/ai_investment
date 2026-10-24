#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
回测 pilot 入口

用法：
    # 链路验证（不调用 LLM，秒级，默认 30 个决策点）
    PYTHONPATH=src .venv/bin/python -m backtest.pilot

    # 真实链路（会调用 LLM，每个决策点约 4-7 分钟）
    PYTHONPATH=src .venv/bin/python -m backtest.pilot --real --assets 600519 --limit 2

    # 用历史成分股作为资产池
    PYTHONPATH=src .venv/bin/python -m backtest.pilot --real --index 000300.SH --universe-limit 3 --limit 2
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import timedelta

from backtest.cache import ResponseCache
from backtest.clock import TradingClock
from backtest.report import render, to_json
from backtest.runner import iter_grid, run_backtest
from backtest.universe import prepare_universe
from utils.pit import parse_date


def _seed(*parts: str) -> int:
    return int(hashlib.md5("|".join(parts).encode("utf-8")).hexdigest(), 16)


def fake_pipeline(asset: str, as_of: str, cache=None) -> dict:
    """确定性假流水线：验证 runner / metrics / 落库，不消耗 LLM"""
    seed = _seed(asset, as_of)
    stance = ("bullish", "neutral", "bearish")[seed % 3]
    conviction = round(0.4 + (seed % 5) / 10, 2)
    executed = bool(seed % 2)
    return {
        "verdict": {
            "stance": stance,
            "conviction": conviction,
            "blind_stance": stance,
            "blind_conviction": conviction,
        },
        "debate": {"enabled": True, "executed": executed, "turns": [{}] if executed else []},
        "verification": {"passed": True, "issues": []},
        "decision_id": f"fake_{seed}",
        "evidence": [{"evidence_id": "EV-0001"}, {"evidence_id": "EV-0002"}, {"evidence_id": "EV-0003"}],
    }


def fake_price_fetcher(asset: str, as_of: str, days: int) -> dict:
    seed = _seed(asset, as_of, str(days))
    ret = ((seed % 2000) - 700) / 10000  # -7% ~ +13%
    return {"entry": 100.0, "exit": 100.0 * (1 + ret), "bars": float(days + 2)}


def real_pipeline(asset: str, as_of: str, cache=None) -> dict:
    from backtest.runner import _default_pipeline

    return _default_pipeline(asset, as_of, cache)


def workday_calendar(start: str, end: str) -> list[str]:
    start_dt = parse_date(start)
    end_dt = parse_date(end)
    days = []
    current = start_dt
    while current <= end_dt + timedelta(days=10):
        if current.weekday() < 5:
            days.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
    return days


def main() -> None:
    parser = argparse.ArgumentParser(description="投研系统回测 pilot")
    parser.add_argument("--real", action="store_true", help="调用真实 Pipeline（耗时长）")
    parser.add_argument("--assets", default="600519", help="逗号分隔的资产代码")
    parser.add_argument("--start", default="2026-01-05")
    parser.add_argument("--end", default="2026-04-30")
    parser.add_argument("--every", type=int, default=3, help="决策点间隔（自然日）")
    parser.add_argument("--limit", type=int, default=30, help="最多跑多少个决策点")
    parser.add_argument("--repeats", type=int, default=None, help="每个决策点重复次数")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--index", default="000300.SH", help="资产池指数（仅 --real 生效）")
    parser.add_argument("--universe-limit", type=int, default=0, help="用历史成分股时的数量上限")
    parser.add_argument("--json", action="store_true", help="同时输出 JSON")
    args = parser.parse_args()

    assets = [item.strip() for item in args.assets.split(",") if item.strip()]
    universe_bias = False

    if args.real and args.universe_limit > 0:
        universe = prepare_universe(args.index, as_of=args.start, limit=args.universe_limit)
        if universe.get("codes"):
            assets = universe["codes"]
        else:
            universe_bias = True
            print(f"⚠ 未取到历史成分股（{universe.get('error')}），样本标记为 universe_bias")

    dates = iter_grid(args.start, args.end, every_n_days=args.every)
    # 每个资产 × 决策点，按 limit 截断总单元数
    max_cells = max(1, int(args.limit))
    assets = assets[: max(1, max_cells // max(1, len(dates)) or 1)]
    dates = dates[: max(1, max_cells // max(1, len(assets)) or 1)]

    repeats = args.repeats if args.repeats is not None else (1 if args.real else 3)
    cache = ResponseCache() if args.real else None
    clock = None
    if not args.real:
        clock = TradingClock(calendar=workday_calendar(args.start, args.end))
    pipeline_fn = real_pipeline if args.real else fake_pipeline
    price_fetcher = None if args.real else fake_price_fetcher

    print(
        f"模式: {'real' if args.real else 'fake'} | 资产: {assets} | "
        f"决策点: {len(dates)} | repeats: {repeats}"
    )
    result = run_backtest(
        assets=assets,
        dates=dates,
        run_id=args.run_id or None,
        repeats=repeats,
        pipeline_fn=pipeline_fn,
        price_fetcher=price_fetcher,
        cache=cache,
        clock=clock,
        universe_bias=universe_bias,
        check_suspension=args.real,
    )
    print(render(result))
    print(f"clock: {result.get('clock')}")
    if args.json:
        print(to_json(result))


if __name__ == "__main__":
    main()
