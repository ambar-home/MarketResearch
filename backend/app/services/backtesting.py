"""
SMA crossover backtester (daily bars).

Execution assumptions (explicit):
- A crossover is detected on the close of day T (signal candle fully complete).
- Entry is at the open of day T+1 (next valid session).
- Exit on opposite crossover detected on day E close, executed at open of E+1.
- Indicators for day T use only data through T (no look-ahead).
- Optional transaction costs + slippage via transaction_costs module.

Research only — not live trading.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from app.config import settings
from app.services import indicators as ind
from app.services.transaction_costs import TransactionCostRates, apply_slippage, estimate_round_trip_costs

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    ticker: str
    side: str
    entry_date: date
    exit_date: date
    entry_price: float
    exit_price: float
    quantity: int
    pnl: float
    return_pct: float
    holding_days: int
    costs: float


def _safe_div(n: float, d: float) -> float | None:
    if d == 0:
        return None
    return n / d


def compute_performance_metrics(
    trades: list[Trade],
    equity_curve: pd.Series,
    initial_capital: float,
    total_costs: float,
) -> dict[str, Any]:
    if not trades:
        return {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": None,
            "average_win_pct": None,
            "average_loss_pct": None,
            "largest_win": None,
            "largest_loss": None,
            "profit_factor": None,
            "expectancy_per_trade": None,
            "total_return_pct": 0.0,
            "cagr_pct": None,
            "max_drawdown_pct": 0.0,
            "sharpe_ratio": None,
            "average_holding_days": None,
            "exposure_pct": None,
            "final_capital": round(initial_capital, 2),
            "transaction_costs": round(total_costs, 2),
            "return_before_costs_pct": None,
            "return_after_costs_pct": 0.0,
        }

    pnls = [t.pnl for t in trades]
    rets = [t.return_pct for t in trades]
    wins = [r for r in rets if r > 0]
    losses = [r for r in rets if r <= 0]
    win_pnls = [p for p in pnls if p > 0]
    loss_pnls = [p for p in pnls if p <= 0]

    gross_profit = sum(win_pnls)
    gross_loss = abs(sum(loss_pnls))
    profit_factor = _safe_div(gross_profit, gross_loss) if gross_loss > 0 else None

    final_capital = float(equity_curve.iloc[-1]) if len(equity_curve) else initial_capital
    total_return_pct = ((final_capital / initial_capital) - 1.0) * 100.0
    return_before_costs_pct = (
        (((final_capital + total_costs) / initial_capital) - 1.0) * 100.0 if initial_capital else None
    )

    cagr_pct = None
    if len(equity_curve) >= 2:
        days = (equity_curve.index[-1] - equity_curve.index[0]).days
        years = days / 365.25 if days > 0 else 0
        if years > 0 and final_capital > 0 and initial_capital > 0:
            cagr_pct = ((final_capital / initial_capital) ** (1 / years) - 1.0) * 100.0

    peak = equity_curve.cummax()
    dd = (equity_curve / peak) - 1.0
    max_dd = float(dd.min() * 100.0) if len(dd) else 0.0

    daily_rets = equity_curve.pct_change().dropna()
    sharpe = None
    if len(daily_rets) > 2 and daily_rets.std() > 0:
        sharpe = float((daily_rets.mean() / daily_rets.std()) * math.sqrt(252))

    held_days = sum(t.holding_days for t in trades)
    total_days = max((equity_curve.index[-1] - equity_curve.index[0]).days, 1)
    exposure_pct = (held_days / total_days) * 100.0

    return {
        "total_trades": len(trades),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "win_rate": round(len(wins) / len(trades) * 100.0, 2),
        "average_win_pct": round(float(np.mean(wins)), 2) if wins else None,
        "average_loss_pct": round(float(np.mean(losses)), 2) if losses else None,
        "largest_win": round(max(pnls), 2),
        "largest_loss": round(min(pnls), 2),
        "profit_factor": round(profit_factor, 3) if profit_factor is not None else None,
        "expectancy_per_trade": round(float(np.mean(pnls)), 2),
        "total_return_pct": round(total_return_pct, 2),
        "cagr_pct": round(cagr_pct, 2) if cagr_pct is not None else None,
        "max_drawdown_pct": round(max_dd, 2),
        "sharpe_ratio": round(sharpe, 3) if sharpe is not None else None,
        "average_holding_days": round(float(np.mean([t.holding_days for t in trades])), 2),
        "exposure_pct": round(exposure_pct, 2),
        "final_capital": round(final_capital, 2),
        "transaction_costs": round(total_costs, 2),
        "return_before_costs_pct": round(return_before_costs_pct, 2)
        if return_before_costs_pct is not None
        else None,
        "return_after_costs_pct": round(total_return_pct, 2),
    }


def backtest_single_symbol(
    df: pd.DataFrame,
    ticker: str,
    short_sma: int,
    long_sma: int,
    initial_capital: float,
    apply_costs: bool,
    slippage_bps: float,
    rates: TransactionCostRates | None = None,
) -> tuple[list[Trade], pd.Series]:
    """Long-only SMA crossover backtest for one symbol (all-in per entry)."""
    rates = rates or settings.costs
    if df.empty or len(df) < long_sma + 5:
        idx = pd.DatetimeIndex([])
        return [], pd.Series(dtype="float64", index=idx)

    data = df.copy().reset_index(drop=True)
    data["date"] = pd.to_datetime(data["date"]).dt.tz_localize(None).dt.normalize()
    data["sma_s"] = ind.sma(data["close"], short_sma)
    data["sma_l"] = ind.sma(data["close"], long_sma)

    cash = float(initial_capital)
    qty = 0
    entry_price = 0.0
    entry_date: date | None = None
    pending: str | None = None
    trades: list[Trade] = []
    equity: list[tuple[pd.Timestamp, float]] = []

    for i in range(len(data)):
        row = data.iloc[i]
        dt = pd.Timestamp(row["date"])

        # 1) Execute pending order at today's open
        if pending == "BUY" and qty == 0:
            raw = float(row["open"])
            px = apply_slippage(raw, "BUY", slippage_bps) if apply_costs else raw
            buy_qty = int(cash // px) if px > 0 else 0
            if buy_qty > 0:
                notional = buy_qty * px
                # Rough buy-side cost = half of estimated round-trip at same price
                buy_cost = 0.0
                if apply_costs:
                    buy_cost = estimate_round_trip_costs(px, px, buy_qty, rates)["total_cost"] / 2.0
                if notional + buy_cost <= cash:
                    cash -= notional + buy_cost
                    qty = buy_qty
                    entry_price = px
                    entry_date = dt.date()
            pending = None

        elif pending == "SELL" and qty > 0 and entry_date is not None:
            raw = float(row["open"])
            px = apply_slippage(raw, "SELL", slippage_bps) if apply_costs else raw
            proceeds = qty * px
            full_costs = (
                estimate_round_trip_costs(entry_price, px, qty, rates)["total_cost"]
                if apply_costs
                else 0.0
            )
            # buy-side half already deducted at entry
            sell_cost = full_costs / 2.0 if apply_costs else 0.0
            cash += proceeds - sell_cost
            pnl = (px - entry_price) * qty - full_costs
            holding = (dt.date() - entry_date).days
            trades.append(
                Trade(
                    ticker=ticker,
                    side="LONG",
                    entry_date=entry_date,
                    exit_date=dt.date(),
                    entry_price=round(entry_price, 2),
                    exit_price=round(px, 2),
                    quantity=qty,
                    pnl=round(pnl, 2),
                    return_pct=round(((px / entry_price) - 1.0) * 100.0, 2) if entry_price else 0.0,
                    holding_days=max(holding, 0),
                    costs=round(full_costs, 2),
                )
            )
            qty = 0
            entry_price = 0.0
            entry_date = None
            pending = None

        # 2) Detect crossover on completed prior bar → queue next open
        if i >= 2:
            prev = data.iloc[i - 1]
            prev2 = data.iloc[i - 2]
            if (
                pd.notna(prev["sma_s"])
                and pd.notna(prev["sma_l"])
                and pd.notna(prev2["sma_s"])
                and pd.notna(prev2["sma_l"])
            ):
                prev_diff = float(prev2["sma_s"]) - float(prev2["sma_l"])
                curr_diff = float(prev["sma_s"]) - float(prev["sma_l"])
                if prev_diff <= 0 and curr_diff > 0 and qty == 0 and pending is None:
                    pending = "BUY"
                elif prev_diff >= 0 and curr_diff < 0 and qty > 0 and pending is None:
                    pending = "SELL"

        equity.append((dt, cash + qty * float(row["close"])))

    # Flatten at last close if still open
    if qty > 0 and entry_date is not None:
        last = data.iloc[-1]
        raw = float(last["close"])
        px = apply_slippage(raw, "SELL", slippage_bps) if apply_costs else raw
        full_costs = (
            estimate_round_trip_costs(entry_price, px, qty, rates)["total_cost"]
            if apply_costs
            else 0.0
        )
        sell_cost = full_costs / 2.0 if apply_costs else 0.0
        cash += qty * px - sell_cost
        pnl = (px - entry_price) * qty - full_costs
        trades.append(
            Trade(
                ticker=ticker,
                side="LONG",
                entry_date=entry_date,
                exit_date=pd.Timestamp(last["date"]).date(),
                entry_price=round(entry_price, 2),
                exit_price=round(px, 2),
                quantity=qty,
                pnl=round(pnl, 2),
                return_pct=round(((px / entry_price) - 1.0) * 100.0, 2),
                holding_days=max((pd.Timestamp(last["date"]).date() - entry_date).days, 0),
                costs=round(full_costs, 2),
            )
        )
        equity[-1] = (equity[-1][0], cash)

    if not equity:
        return trades, pd.Series([initial_capital], index=[pd.Timestamp.now()])
    idx, vals = zip(*equity)
    return trades, pd.Series(vals, index=pd.DatetimeIndex(idx))


def run_sma_backtest(
    price_frames: dict[str, pd.DataFrame],
    short_sma: int,
    long_sma: int,
    start_date: str,
    end_date: str,
    initial_capital: float = 1_000_000,
    transaction_costs: bool = True,
    slippage_bps: float | None = None,
) -> dict[str, Any]:
    logger.info(
        "backtest_started short=%s long=%s start=%s end=%s symbols=%s",
        short_sma,
        long_sma,
        start_date,
        end_date,
        len(price_frames),
    )

    if short_sma < 2 or long_sma <= short_sma:
        raise ValueError("Invalid SMA periods: require long_sma > short_sma >= 2")
    if initial_capital <= 0:
        raise ValueError("Initial capital must be > 0")

    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)
    if end <= start:
        raise ValueError("end_date must be after start_date")

    slip = settings.costs.slippage_bps if slippage_bps is None else float(slippage_bps)
    if slip < 0:
        raise ValueError("Slippage must be >= 0")

    base = settings.costs
    rates = TransactionCostRates(
        brokerage_rate=base.brokerage_rate,
        brokerage_cap=base.brokerage_cap,
        stt_buy_rate=base.stt_buy_rate,
        stt_sell_rate=base.stt_sell_rate,
        exchange_txn_rate=base.exchange_txn_rate,
        sebi_rate=base.sebi_rate,
        stamp_duty_buy_rate=base.stamp_duty_buy_rate,
        gst_on_brokerage_and_txn=base.gst_on_brokerage_and_txn,
        slippage_bps=slip,
    )

    symbols = sorted(price_frames.keys())
    if not symbols:
        raise ValueError("No price data provided for backtest")

    per_capital = initial_capital / len(symbols)
    all_trades: list[Trade] = []
    excess_parts: list[pd.Series] = []

    for ticker in symbols:
        df = price_frames[ticker].copy()
        df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None).dt.normalize()
        df = df[(df["date"] >= start) & (df["date"] <= end)].reset_index(drop=True)
        trades, eq = backtest_single_symbol(
            df=df,
            ticker=ticker,
            short_sma=short_sma,
            long_sma=long_sma,
            initial_capital=per_capital,
            apply_costs=transaction_costs,
            slippage_bps=slip,
            rates=rates,
        )
        all_trades.extend(trades)
        if not eq.empty:
            excess_parts.append(eq - per_capital)

    if excess_parts:
        combined = excess_parts[0]
        for part in excess_parts[1:]:
            combined = combined.add(part, fill_value=0.0)
        equity_curve = combined + initial_capital
    else:
        equity_curve = pd.Series([initial_capital], index=[start])

    total_costs = sum(t.costs for t in all_trades)
    metrics = compute_performance_metrics(all_trades, equity_curve, initial_capital, total_costs)

    equity_list = [
        {"date": ts.date().isoformat(), "equity": round(float(val), 2)}
        for ts, val in equity_curve.items()
    ]
    peak = equity_curve.cummax()
    dd = ((equity_curve / peak) - 1.0) * 100.0
    drawdown_list = [
        {"date": ts.date().isoformat(), "drawdown_pct": round(float(val), 2)}
        for ts, val in dd.items()
    ]

    trade_rows = [
        {
            "ticker": t.ticker,
            "side": t.side,
            "entry_date": t.entry_date.isoformat(),
            "exit_date": t.exit_date.isoformat(),
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "quantity": t.quantity,
            "pnl": t.pnl,
            "return_pct": t.return_pct,
            "holding_days": t.holding_days,
            "costs": t.costs,
        }
        for t in sorted(all_trades, key=lambda x: x.exit_date)
    ]

    span_days = (end - start).days
    train_end = start + pd.Timedelta(days=int(span_days * 0.6))
    val_end = start + pd.Timedelta(days=int(span_days * 0.8))

    logger.info(
        "backtest_completed trades=%s return=%.2f drawdown=%.2f",
        metrics["total_trades"],
        metrics["total_return_pct"] or 0,
        metrics["max_drawdown_pct"] or 0,
    )

    return {
        "params": {
            "short_sma": short_sma,
            "long_sma": long_sma,
            "start_date": start_date,
            "end_date": end_date,
            "initial_capital": initial_capital,
            "transaction_costs": transaction_costs,
            "slippage_bps": slip,
            "symbols": len(symbols),
        },
        "execution_assumptions": [
            "Crossover detected on completed daily close (day T).",
            "Entry/exit executed at next session open (day T+1 / E+1).",
            "Long-only research model; equal capital split across symbols.",
            "Costs/slippage optional and configurable.",
            "No look-ahead bias in signal detection.",
        ],
        "metrics": metrics,
        "equity_curve": equity_list,
        "drawdown_curve": drawdown_list,
        "trades": trade_rows,
        "segments": {
            "training": {"start": start.date().isoformat(), "end": train_end.date().isoformat()},
            "validation": {
                "start": (train_end + pd.Timedelta(days=1)).date().isoformat(),
                "end": val_end.date().isoformat(),
            },
            "out_of_sample": {
                "start": (val_end + pd.Timedelta(days=1)).date().isoformat(),
                "end": end.date().isoformat(),
            },
            "note": "Segments are chronological. Do not shuffle time-series data.",
        },
        "disclaimer": (
            "Backtest results are hypothetical research outputs based on historical data "
            "and configurable assumptions. Past performance does not guarantee future results."
        ),
    }


DEFAULT_SMA_COMBOS = [
    (5, 20),
    (6, 20),
    (6, 30),
    (10, 30),
    (10, 50),
    (20, 50),
    (20, 100),
    (50, 200),
]


def compare_sma_combos(
    price_frames: dict[str, pd.DataFrame],
    start_date: str,
    end_date: str,
    initial_capital: float,
    transaction_costs: bool,
    slippage_bps: float,
    combos: list[tuple[int, int]] | None = None,
) -> dict[str, Any]:
    combos = combos or DEFAULT_SMA_COMBOS
    rows = []
    for short_sma, long_sma in combos:
        if long_sma <= short_sma:
            continue
        try:
            result = run_sma_backtest(
                price_frames=price_frames,
                short_sma=short_sma,
                long_sma=long_sma,
                start_date=start_date,
                end_date=end_date,
                initial_capital=initial_capital,
                transaction_costs=transaction_costs,
                slippage_bps=slippage_bps,
            )
            m = result["metrics"]
            rows.append(
                {
                    "strategy": f"{short_sma}/{long_sma}",
                    "short_sma": short_sma,
                    "long_sma": long_sma,
                    "total_return_pct": m["total_return_pct"],
                    "max_drawdown_pct": m["max_drawdown_pct"],
                    "win_rate": m["win_rate"],
                    "profit_factor": m["profit_factor"],
                    "sharpe_ratio": m["sharpe_ratio"],
                    "total_trades": m["total_trades"],
                    "cagr_pct": m["cagr_pct"],
                }
            )
        except Exception as exc:
            logger.warning("Combo %s/%s failed: %s", short_sma, long_sma, exc)
            rows.append(
                {
                    "strategy": f"{short_sma}/{long_sma}",
                    "short_sma": short_sma,
                    "long_sma": long_sma,
                    "error": str(exc),
                }
            )

    return {
        "comparisons": rows,
        "note": (
            "Highest return is not automatically best. Prefer risk-adjusted metrics "
            "(drawdown, Sharpe, profit factor) and out-of-sample validation."
        ),
    }
