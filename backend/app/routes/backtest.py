"""Backtesting endpoints — research only, no live orders."""

from __future__ import annotations

import logging
import time
from datetime import datetime

import pandas as pd
from fastapi import APIRouter, HTTPException

from app.schemas import BacktestRequest, BacktestResponse
from app.services.backtesting import compare_sma_combos, run_sma_backtest
from app.services.kite_session import kite_session
from app.services.sma_scanner import download_scan_universe, fetch_daily_history, map_symbols_to_tokens

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


@router.post("/sma", response_model=BacktestResponse)
def backtest_sma(body: BacktestRequest) -> BacktestResponse:
    if not kite_session.is_authenticated:
        raise HTTPException(status_code=401, detail="Not authenticated. Please log in.")

    if body.long_sma <= body.short_sma:
        raise HTTPException(status_code=400, detail="Long SMA must be greater than Short SMA.")

    try:
        start = datetime.strptime(body.start_date, "%Y-%m-%d").date()
        end = datetime.strptime(body.end_date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Dates must be YYYY-MM-DD") from exc

    if end <= start:
        raise HTTPException(status_code=400, detail="end_date must be after start_date")

    # Need enough calendar span for long SMA
    if (end - start).days < body.long_sma + 30:
        raise HTTPException(
            status_code=400,
            detail=f"Backtest period too short for SMA {body.long_sma}. Use a longer date range.",
        )

    kite = kite_session.get_kite()

    try:
        universe = download_scan_universe(body.max_stocks)
        symbols = universe.head(body.max_stocks)["Symbol"].tolist()
        token_map = map_symbols_to_tokens(kite, symbols)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Universe/instrument mapping failed: {exc}") from exc

    lookback_days = (end - start).days + body.long_sma + 40
    frames: dict[str, pd.DataFrame] = {}
    for symbol, token in token_map.items():
        try:
            hist = fetch_daily_history(kite, token, lookback_days)
            if hist.empty:
                continue
            frames[symbol] = hist
        except Exception as exc:
            logger.warning("backtest history failed for %s: %s", symbol, exc)
        time.sleep(0.2)

    if not frames:
        raise HTTPException(status_code=502, detail="No historical candles available for backtest.")

    try:
        result = run_sma_backtest(
            price_frames=frames,
            short_sma=body.short_sma,
            long_sma=body.long_sma,
            start_date=body.start_date,
            end_date=body.end_date,
            initial_capital=body.initial_capital,
            transaction_costs=body.transaction_costs,
            slippage_bps=body.slippage_bps,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Backtest failed: {exc}") from exc

    comparisons = None
    comparison_note = None
    if body.compare_combos:
        cmp = compare_sma_combos(
            price_frames=frames,
            start_date=body.start_date,
            end_date=body.end_date,
            initial_capital=body.initial_capital,
            transaction_costs=body.transaction_costs,
            slippage_bps=body.slippage_bps,
        )
        comparisons = cmp["comparisons"]
        comparison_note = cmp["note"]

    return BacktestResponse(
        params=result["params"],
        execution_assumptions=result["execution_assumptions"],
        metrics=result["metrics"],
        equity_curve=result["equity_curve"],
        drawdown_curve=result["drawdown_curve"],
        trades=result["trades"],
        segments=result.get("segments"),
        comparisons=comparisons,
        comparison_note=comparison_note,
        disclaimer=result.get("disclaimer"),
    )
