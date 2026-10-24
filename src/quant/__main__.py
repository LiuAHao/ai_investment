#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
轻量量化回测

用法：
    PYTHONPATH=src .venv/bin/python -m quant --assets 600519 \
        --start 2020-01-01 --end 2026-06-30 --strategy ma_cross

    PYTHONPATH=src .venv/bin/python -m quant --assets 600519,000858 \
        --strategy momentum --params '{"lookback": 20}' --json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta

from quant.data import load_prices
from quant.engine import run_portfolio
from quant.report import render, render_trades, to_json
from quant.strategies import STRATEGIES


def _parse_params(raw: str) -> dict:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"--params 不是合法 JSON: {exc}")
    if not isinstance(value, dict):
        raise SystemExit("--params 必须是 JSON 对象")
    return value


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m quant",
        description="轻量量化回测：日线、只做多、T+1 开盘成交",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""内置策略与参数（--params 传 JSON）:
  buy_hold   无参数，始终满仓持有
  ma_cross   fast=20, slow=60（快线在慢线上方时持有）
  momentum   lookback=20（近 N 日收益为正时持有）

成交与成本规则:
  T 日收盘产生信号 → T+1 开盘成交；A 股 100 股一手
  手续费 = max(成交额 × --fee, --min-fee)，买卖双边
  滑点：买入价 ×(1+slip)，卖出价 ×(1-slip)

示例:
  python -m quant --assets 600519 --strategy ma_cross --params '{"fast":20,"slow":60}'
  python -m quant --assets 600519,000858 --strategy momentum --params '{"lookback":20}' --json
  python -m quant --assets 510300 --start 2022-01-01 --end 2025-12-31 --benchmark ''
""",
    )
    today = date.today()
    parser.add_argument("--assets", default="600519", help="逗号分隔的代码，支持 A 股 / ETF / 指数")
    parser.add_argument("--start", default=(today - timedelta(days=365 * 5)).isoformat(), help="开始日期 YYYY-MM-DD（默认 5 年前）")
    parser.add_argument("--end", default=today.isoformat(), help="结束日期 YYYY-MM-DD（默认今天）")
    parser.add_argument("--strategy", default="ma_cross", choices=sorted(STRATEGIES), help="内置策略")
    parser.add_argument("--params", default="", help='策略参数 JSON，例如 {"fast":20,"slow":60}')
    parser.add_argument("--cash", type=float, default=1_000_000.0, help="初始资金（高价股一手可能超过 10 万）")
    parser.add_argument("--fee", type=float, default=0.00025, help="手续费率（单边，默认万 2.5）")
    parser.add_argument("--min-fee", type=float, default=5.0, help="单笔最低手续费（默认 5 元）")
    parser.add_argument("--slippage", type=float, default=0.001, help="滑点比例（单边，默认 0.1%%）")
    parser.add_argument("--benchmark", default="000300", help="基准代码（默认沪深300；空字符串关闭）")
    parser.add_argument("--no-cache", action="store_true", help="不使用本地行情缓存，强制重新拉取")
    parser.add_argument("--json", action="store_true", help="额外输出 JSON（含净值曲线）")
    parser.add_argument("--trades", type=int, default=0, help="展示前 N 笔交易（0=不展示）")
    args = parser.parse_args(argv)

    assets = [item.strip() for item in args.assets.split(",") if item.strip()]
    params = _parse_params(args.params)

    frames = {}
    for asset in assets:
        try:
            frames[asset] = load_prices(asset, args.start, args.end, use_cache=not args.no_cache)
        except Exception as exc:
            print(f"⚠ 跳过 {asset}: {exc}", file=sys.stderr)
    if not frames:
        raise SystemExit("没有可用资产")

    benchmark_equity = None
    if args.benchmark:
        try:
            bench = load_prices(
                args.benchmark, args.start, args.end,
                use_cache=not args.no_cache, kind="index",
            )
            benchmark_equity = bench.set_index("date")["close"]
        except Exception as exc:
            print(f"⚠ 基准 {args.benchmark} 不可用: {exc}", file=sys.stderr)

    result = run_portfolio(
        frames=frames,
        strategy=args.strategy,
        strategy_params=params,
        cash=args.cash,
        fee_rate=args.fee,
        min_fee=args.min_fee,
        slippage=args.slippage,
        benchmark_equity=benchmark_equity,
    )

    print(render(result))
    if args.trades > 0:
        print()
        print(render_trades(result, limit=args.trades))
    if args.json:
        print()
        print(to_json(result, include_trades=args.trades > 0))


if __name__ == "__main__":
    main()
