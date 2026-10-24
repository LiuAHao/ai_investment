import pandas as pd
import pytest

from quant.engine import run_backtest, run_portfolio
from quant.metrics import max_drawdown
from quant.strategies import buy_hold, ma_cross, momentum


def make_df(prices, opens=None):
    dates = pd.date_range("2024-01-01", periods=len(prices), freq="D")
    return pd.DataFrame({
        "date": dates,
        "open": opens if opens is not None else prices,
        "high": prices,
        "low": prices,
        "close": prices,
        "volume": [1000] * len(prices),
    })


def test_t_plus_one_execution():
    df = make_df([10, 11, 12, 13])
    signals = pd.Series([0, 1, 0, 0])
    result = run_backtest(df, signals, cash=100_000, fee_rate=0, min_fee=0, slippage=0)
    buys = [t for t in result.trades if t["side"] == "buy"]
    assert len(buys) == 1
    # 信号在 index=1 收盘产生，应在 index=2 开盘成交
    assert buys[0]["date"] == "2024-01-03"
    assert buys[0]["price"] == 12


def test_buy_hold_return_matches_price():
    df = make_df([10, 11, 12, 13, 14])
    result = run_backtest(df, buy_hold(df), cash=100_000, fee_rate=0, min_fee=0, slippage=0)
    # T+1 从 11 买入；整手取整后持有 9000 股，剩余 1000 现金
    expected = (9000 * 14 + 1000) / 100_000 - 1
    assert result.metrics["total_return"] == pytest.approx(expected, rel=1e-9)


def test_costs_reduce_return():
    df = make_df([10, 11, 12, 13, 14])
    free = run_backtest(df, buy_hold(df), cash=100_000, fee_rate=0, min_fee=0, slippage=0)
    paid = run_backtest(df, buy_hold(df), cash=100_000, fee_rate=0.001, min_fee=5, slippage=0.001)
    assert paid.metrics["total_return"] < free.metrics["total_return"]
    assert paid.metrics["trades"] == 1


def test_max_drawdown():
    equity = pd.Series([100, 120, 90, 110])
    assert max_drawdown(equity) == pytest.approx(90 / 120 - 1)


def test_ma_cross_produces_long_only_signals():
    prices = [10, 11, 12, 13, 14, 13, 12, 11, 10, 11, 12, 13, 14, 15]
    df = make_df(prices)
    signals = ma_cross(df, fast=2, slow=4)
    assert set(signals.unique()).issubset({0, 1})
    assert len(signals) == len(df)


def test_momentum_signals():
    df = make_df([10, 11, 12, 11, 13, 14])
    signals = momentum(df, lookback=2)
    assert int(signals.iloc[2]) == 1
    assert int(signals.iloc[3]) == 0


def test_portfolio_combines_assets():
    a = make_df([10, 11, 12, 13, 14])
    b = make_df([20, 21, 22, 21, 23])
    result = run_portfolio(
        {"A": a, "B": b},
        strategy="buy_hold",
        cash=100_000,
        fee_rate=0,
        min_fee=0,
        slippage=0,
    )
    assert result.metrics["total_return"] > 0
    assert result.metrics["final_equity"] > 100_000
    assert len(result.trades) == 4
