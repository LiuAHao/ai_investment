#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
回测运行器

- 决策点遍历（自然日间隔）
- PIT 数据源（禁用新闻类工具）
- 幂等与断点续跑（SQLite 落库，按 run_id + asset + as_of）
- 多次运行取多数方向，标记不稳定样本
"""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from backtest import metrics
from backtest.cache import ResponseCache
from backtest.clock import TradingClock
from backtest.datasource import pit_datasource
from memory.settlement import _default_price_fetcher, compute_alpha, compute_return, horizon_days
from utils.pit import parse_date

logger = logging.getLogger(__name__)

DB_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "backtest.sqlite")
)
_LOCK = threading.Lock()

PipelineFn = Callable[[str, str, Optional[ResponseCache]], Dict[str, Any]]
PriceFetcher = Callable[[str, str, int], Dict[str, float]]


def iter_grid(start: str, end: str, every_n_days: int = 7) -> List[str]:
    """生成决策点（按自然日间隔）"""
    start_dt = parse_date(start)
    end_dt = parse_date(end)
    if not start_dt or not end_dt:
        return []
    step = max(1, int(every_n_days))
    dates: List[str] = []
    current = start_dt
    while current <= end_dt:
        dates.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=step)
    return dates


def run_backtest(
    assets: List[str],
    dates: List[str],
    run_id: Optional[str] = None,
    repeats: int = 1,
    pipeline_fn: Optional[PipelineFn] = None,
    price_fetcher: Optional[PriceFetcher] = None,
    cache: Optional[ResponseCache] = None,
    clock: Optional[TradingClock] = None,
    resume: bool = True,
    allow_news: bool = False,
    universe_bias: bool = False,
    horizon: str = "medium",
    check_suspension: bool = False,
) -> Dict[str, Any]:
    """
    执行回测。

    Returns:
        {run_id, records, summary, universe_bias, clock}
    """
    run_id = run_id or f"bt_{uuid.uuid4().hex[:8]}"
    pipeline_fn = pipeline_fn or _default_pipeline
    price_fetcher = price_fetcher or _default_price_fetcher
    clock = clock or TradingClock.from_tushare(
        start=dates[0] if dates else "2020-01-01",
        end=(parse_date(dates[-1]) + timedelta(days=400)).strftime("%Y-%m-%d") if dates else "2030-01-01",
    )
    _init_db()

    prev_settle = os.environ.get("SETTLE_ON_START")
    os.environ["SETTLE_ON_START"] = "0"
    records: List[Dict[str, Any]] = []
    try:
        for asset in assets:
            for as_of in dates:
                if not clock.is_trading_day(as_of):
                    continue
                if resume:
                    existing = _load_cell(run_id, asset, as_of)
                    if existing:
                        records.append(existing)
                        continue
                record = _run_cell(
                    asset=asset,
                    as_of=as_of,
                    run_id=run_id,
                    repeats=repeats,
                    pipeline_fn=pipeline_fn,
                    price_fetcher=price_fetcher,
                    cache=cache,
                    horizon=horizon,
                    allow_news=allow_news,
                    clock=clock,
                    check_suspension=check_suspension,
                )
                if record:
                    _save_cell(record)
                    records.append(record)
    finally:
        if prev_settle is None:
            os.environ.pop("SETTLE_ON_START", None)
        else:
            os.environ["SETTLE_ON_START"] = prev_settle

    summary = metrics.summarize(records)
    if universe_bias:
        summary["universe_bias"] = True
    return {
        "run_id": run_id,
        "records": records,
        "summary": summary,
        "universe_bias": universe_bias,
        "clock": clock.describe(),
    }


def _run_cell(
    asset: str,
    as_of: str,
    run_id: str,
    repeats: int,
    pipeline_fn: PipelineFn,
    price_fetcher: PriceFetcher,
    cache: Optional[ResponseCache],
    horizon: str,
    allow_news: bool,
    clock: Optional[TradingClock] = None,
    check_suspension: bool = False,
) -> Optional[Dict[str, Any]]:
    execution = clock.execution_date(as_of, "buy") if clock else None
    if clock is not None and execution is None:
        logger.warning("回测单元无法成交 %s %s（停牌/涨跌停顺延失败）", asset, as_of)
        return None
    if check_suspension and clock is not None:
        execution = _adjust_for_suspension(asset, execution, clock)
        if execution is None:
            logger.warning("回测单元连续停牌，放弃 %s %s", asset, as_of)
            return None

    stances: List[str] = []
    convictions: List[float] = []
    debate_flags: List[bool] = []
    degraded = False
    decision_id = ""
    evidence_count = 0

    total_runs = max(1, int(repeats))
    for run_index in range(total_runs):
        try:
            # 第一次可用缓存（跨 run 复现），后续运行绕过缓存以检测 LLM 非确定性
            use_cache = cache if run_index == 0 else None
            with pit_datasource(as_of, allow_news=allow_news):
                result = pipeline_fn(asset, as_of, use_cache)
            verdict = result.get("verdict") or {}
            stances.append(str(verdict.get("stance") or "neutral"))
            convictions.append(float(verdict.get("conviction") or 0.0))
            debate_flags.append(bool((result.get("debate") or {}).get("executed")))
            degraded = degraded or not bool((result.get("verification") or {}).get("passed", True))
            decision_id = str(result.get("decision_id") or decision_id)
            evidence_count = int(len(result.get("evidence") or []))
        except Exception as exc:  # noqa: BLE001
            logger.warning("回测单元失败 %s %s: %s", asset, as_of, exc)
            return None

    stance = metrics.majority_stance(stances)
    unstable = metrics.is_unstable(stances)
    conviction = sum(convictions) / len(convictions) if convictions else 0.0

    days = horizon_days(horizon)
    try:
        prices = price_fetcher(asset, as_of, days)
        bench_prices = price_fetcher("000300", as_of, days)
    except Exception as exc:  # noqa: BLE001
        logger.warning("回测取价失败 %s %s: %s", asset, as_of, exc)
        return None
    if not prices.get("entry") or not prices.get("exit"):
        return None

    ret = compute_return(prices["entry"], prices["exit"])
    bench_ret = None
    if bench_prices.get("entry") and bench_prices.get("exit"):
        bench_ret = compute_return(bench_prices["entry"], bench_prices["exit"])
    alpha = compute_alpha(ret, bench_ret)

    return {
        "run_id": run_id,
        "asset": asset,
        "as_of": as_of,
        "execution_date": execution or as_of,
        "stance": stance,
        "conviction": round(conviction, 4),
        "ret": round(ret, 6),
        "benchmark_ret": round(bench_ret, 6) if bench_ret is not None else None,
        "alpha": round(alpha, 6) if alpha is not None else None,
        "hit": metrics.is_hit(stance, ret),
        "debate_enabled": all(debate_flags) if debate_flags else False,
        "unstable": unstable,
        "stances": stances,
        "degraded": degraded,
        "decision_id": decision_id,
        "evidence_count": evidence_count,
        "horizon_days": days,
    }


def _adjust_for_suspension(
    asset: str,
    execution: Optional[str],
    clock: TradingClock,
    max_delay: int = 3,
) -> Optional[str]:
    """成交日遇到停牌时顺延（涨跌停判定仍需当日价格，暂未接入）"""
    if not execution:
        return None
    try:
        from data.tushare_client import _normalize_symbol, _ts_code, get_client

        client = get_client()
        code = _ts_code(_normalize_symbol(asset), "stock")
        if client is None or not code:
            return execution
        current = parse_date(execution)
        for _ in range(max_delay + 1):
            if current is None:
                return None
            try:
                df = client.suspend_d(trade_date=current.strftime("%Y%m%d"))
                suspended = set(df["ts_code"].astype(str)) if df is not None and not df.empty else set()
            except Exception as exc:  # noqa: BLE001
                logger.info("停牌检查失败，保留原成交日: %s", str(exc)[:80])
                return execution
            if code not in suspended:
                return current.isoformat()
            current = clock.next_trading_day(current)
    except Exception as exc:  # noqa: BLE001
        logger.info("停牌检查异常，保留原成交日: %s", str(exc)[:80])
        return execution
    return None


def _default_pipeline(asset: str, as_of: str, cache: Optional[ResponseCache]) -> Dict[str, Any]:
    """
    结果级缓存：分析师 ReAct 循环不走 LLM 缓存，仅靠调用级缓存无法复现；
    这里按 (资产, 时点, 模型) 缓存完整结果，保证同一 run 重跑一致。
    """
    import json

    from agents.pipeline import Pipeline

    cache_key = f"pipeline|{asset}|{as_of}|{os.getenv('AGENT_LLM_MODEL', '')}"
    if cache is not None:
        try:
            cached = cache.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception as exc:  # noqa: BLE001
            logger.warning("结果缓存读取失败: %s", exc)

    result = Pipeline(cache=cache).run(
        session_id=f"backtest:{asset}:{as_of}",
        query=f"{asset} 未来走势与投资价值分析",
        as_of=as_of,
    )
    if cache is not None:
        try:
            cache.set(cache_key, json.dumps(result, ensure_ascii=False, default=str))
        except Exception as exc:  # noqa: BLE001
            logger.warning("结果缓存写入失败: %s", exc)
    return result


# ---------- 存储 ----------

def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db() -> None:
    with _LOCK, _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS backtest_results (
                run_id TEXT,
                asset TEXT,
                as_of TEXT,
                payload TEXT,
                created_at TEXT,
                PRIMARY KEY (run_id, asset, as_of)
            )
        """)
        conn.commit()


def _save_cell(record: Dict[str, Any]) -> None:
    import json

    with _LOCK, _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO backtest_results (run_id, asset, as_of, payload, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                record["run_id"], record["asset"], record["as_of"],
                json.dumps(record, ensure_ascii=False, default=str),
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        conn.commit()


def _load_cell(run_id: str, asset: str, as_of: str) -> Optional[Dict[str, Any]]:
    import json

    with _connect() as conn:
        row = conn.execute(
            "SELECT payload FROM backtest_results WHERE run_id = ? AND asset = ? AND as_of = ?",
            (run_id, asset, as_of),
        ).fetchone()
    if not row:
        return None
    try:
        return json.loads(row["payload"])
    except Exception:  # noqa: BLE001
        return None


def load_results(run_id: str) -> List[Dict[str, Any]]:
    import json

    _init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT payload FROM backtest_results WHERE run_id = ? ORDER BY asset, as_of",
            (run_id,),
        ).fetchall()
    output = []
    for row in rows:
        try:
            output.append(json.loads(row["payload"]))
        except Exception:  # noqa: BLE001
            continue
    return output
