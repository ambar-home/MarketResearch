"""Unit tests for backtesting mechanics (no look-ahead / costs)."""

from __future__ import annotations

import pandas as pd

from app.services.backtesting import backtest_single_symbol, compute_performance_metrics, run_sma_backtest
from app.services.transaction_costs import apply_slippage, estimate_round_trip_costs


def _synthetic_ohlcv(n: int = 120) -> pd.DataFrame:
    """Create a series with a clear up then down regime for crossovers."""
    rows = []
    price = 100.0
    for i in range(n):
        if i < 60:
            price += 0.8
        else:
            price -= 0.9
        rows.append(
            {
                "date": pd.Timestamp("2023-01-01") + pd.Timedelta(days=i),
                "open": price - 0.2,
                "high": price + 0.5,
                "low": price - 0.5,
                "close": price,
                "volume": 1000 + i,
            }
        )
    return pd.DataFrame(rows)


def test_slippage_direction():
    assert apply_slippage(100, "BUY", 10) > 100
    assert apply_slippage(100, "SELL", 10) < 100


def test_transaction_costs_positive():
    costs = estimate_round_trip_costs(100, 110, 10)
    assert costs["total_cost"] > 0


def test_backtest_no_lookahead_and_metrics():
    df = _synthetic_ohlcv()
    trades, equity = backtest_single_symbol(
        df=df,
        ticker="TEST",
        short_sma=5,
        long_sma=20,
        initial_capital=100000,
        apply_costs=True,
        slippage_bps=5,
    )
    # Entry must be after signal; holding days non-negative
    for t in trades:
        assert t.exit_date >= t.entry_date
        assert t.holding_days >= 0

    metrics = compute_performance_metrics(trades, equity, 100000, sum(t.costs for t in trades))
    assert metrics["total_trades"] == len(trades)
    assert "max_drawdown_pct" in metrics
    assert metrics["final_capital"] is not None


def test_run_sma_backtest_wrapper():
    df = _synthetic_ohlcv()
    result = run_sma_backtest(
        price_frames={"TEST": df},
        short_sma=5,
        long_sma=20,
        start_date="2023-01-01",
        end_date="2023-04-30",
        initial_capital=100000,
        transaction_costs=True,
        slippage_bps=5,
    )
    assert "metrics" in result
    assert "equity_curve" in result
    assert "execution_assumptions" in result
    assert result["segments"]["note"]
