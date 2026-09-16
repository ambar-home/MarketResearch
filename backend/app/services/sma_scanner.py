"""
Enhanced SMA crossover research scanner.

Universe:
  - Max Stocks <= 100 → official Nifty 100 list
  - Max Stocks 101–200 → official Nifty 200 list

Uses server-side Kite session. Never exposes access_token.
Produces scored research candidates — not trade instructions.
"""

from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta
from io import StringIO
from typing import Any

import pandas as pd
import requests
from kiteconnect import KiteConnect

from app.config import KITE_SLEEP_SECONDS, NIFTY100_CSV_URL, NIFTY200_CSV_URL, settings
from app.services import indicators as ind
from app.services.kite_session import kite_session
from app.services.market_context import MarketContextCache
from app.services.signal_engine import build_risk_reward, score_signal

logger = logging.getLogger(__name__)

_NSE_CSV_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/csv,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}


def _download_index_constituents(url: str, label: str) -> pd.DataFrame:
    """Load official Nifty Indices CSV and normalize Symbol/Company columns."""
    response = requests.get(url, headers=_NSE_CSV_HEADERS, timeout=30)
    response.raise_for_status()

    frame = pd.read_csv(StringIO(response.text))
    if "Symbol" not in frame.columns:
        raise ValueError(f"Unexpected {label} CSV columns: {list(frame.columns)}")

    if "Company Name" in frame.columns:
        frame = frame.rename(columns={"Company Name": "Company"})
    elif "Company" not in frame.columns:
        frame["Company"] = frame["Symbol"]

    frame["Symbol"] = frame["Symbol"].astype(str).str.strip().str.upper()
    frame["Company"] = frame["Company"].astype(str).str.strip()
    return frame[["Symbol", "Company"]].drop_duplicates(subset=["Symbol"], keep="first")


def download_nifty100() -> pd.DataFrame:
    """Load official Nifty 100 constituents."""
    return _download_index_constituents(NIFTY100_CSV_URL, "Nifty 100")


def download_nifty200() -> pd.DataFrame:
    """Load official Nifty 200 constituents (supports Max Stocks up to 200)."""
    return _download_index_constituents(NIFTY200_CSV_URL, "Nifty 200")


def download_scan_universe(max_stocks: int) -> pd.DataFrame:
    """
    Choose universe large enough for the requested max_stocks.
    - max_stocks <= 100 → Nifty 100 (faster / classic list)
    - max_stocks > 100  → Nifty 200 (so 101–200 can actually be scanned)
    """
    if max_stocks > 100:
        universe = download_nifty200()
        source = "NIFTY 200"
    else:
        universe = download_nifty100()
        source = "NIFTY 100"

    if universe.empty:
        raise ValueError(f"{source} constituent list is empty.")

    logger.info(
        "universe_loaded source=%s available=%s requested=%s",
        source,
        len(universe),
        max_stocks,
    )
    universe.attrs["source"] = source
    return universe


def map_symbols_to_tokens(kite: KiteConnect, symbols: list[str]) -> dict[str, int]:
    instruments = kite.instruments("NSE")
    instruments_df = pd.DataFrame(instruments)

    eq = instruments_df[
        (instruments_df["tradingsymbol"].isin(symbols))
        & (instruments_df["instrument_type"] == "EQ")
        & (instruments_df["segment"] == "NSE")
    ].drop_duplicates(subset=["tradingsymbol"], keep="first")

    return dict(zip(eq["tradingsymbol"], eq["instrument_token"]))


def fetch_daily_history(
    kite: KiteConnect,
    instrument_token: int,
    lookback_days: int,
) -> pd.DataFrame:
    to_date = datetime.now().date()
    from_date = to_date - timedelta(days=lookback_days)

    candles = kite.historical_data(
        instrument_token=instrument_token,
        from_date=from_date,
        to_date=to_date,
        interval="day",
        continuous=False,
        oi=False,
    )
    if not candles:
        return pd.DataFrame()

    df = pd.DataFrame(candles)
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None).dt.normalize()
    return df.sort_values("date").reset_index(drop=True)


def analyze_stock_history(
    df: pd.DataFrame,
    *,
    short_sma: int,
    long_sma: int,
    rsi_period: int,
    volume_period: int,
    atr_period: int,
    slope_lookback: int,
    market_trend: str,
    sector_info: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Build a full research signal for the latest crossover in `df`.
    Returns None if no crossover / insufficient data.
    """
    required = {"date", "open", "high", "low", "close", "volume"}
    if df.empty or not required.issubset(df.columns):
        return None

    min_rows = max(long_sma + slope_lookback + 5, rsi_period + 5, atr_period + 5, volume_period + 5)
    if len(df) < min_rows:
        return None

    short_series = ind.sma(df["close"], short_sma)
    long_series = ind.sma(df["close"], long_sma)
    event = ind.detect_crossover(short_series, long_series)
    if event is None:
        return None

    idx = event["index"]
    # Align to integer position
    pos = df.index.get_loc(idx) if idx in df.index else int(idx)
    if isinstance(pos, slice):
        return None

    row = df.iloc[pos]
    close = float(row["close"])
    short_val = float(short_series.iloc[pos])
    long_val = float(long_series.iloc[pos])
    crossover_date = pd.Timestamp(row["date"]).date()
    days_since = (datetime.now().date() - crossover_date).days

    # Use full series ending at crossover bar for contextual indicators
    hist = df.iloc[: pos + 1].copy()
    short_to_date = ind.sma(hist["close"], short_sma)
    long_to_date = ind.sma(hist["close"], long_sma)
    slope = ind.long_sma_slope(long_to_date, lookback=slope_lookback)
    price_ctx = ind.price_vs_long_sma(close, long_val)
    ext = ind.extension_status(close, short_val)
    vol = ind.volume_metrics(hist["volume"], period=volume_period)

    rsi_series = ind.rsi_wilder(hist["close"], period=rsi_period)
    rsi_val = float(rsi_series.dropna().iloc[-1]) if rsi_series.dropna().size else None
    rsi_status = ind.momentum_status(rsi_val, event["type"])

    atr_series = ind.atr_wilder(hist["high"], hist["low"], hist["close"], period=atr_period)
    atr_val = float(atr_series.dropna().iloc[-1]) if atr_series.dropna().size else None
    atr_pct = ind.atr_pct(atr_val, close)

    swing_low = ind.latest_swing_low(hist["low"])
    swing_high = ind.latest_swing_high(hist["high"])
    rr = build_risk_reward(
        side=event["type"],
        close=close,
        atr_value=atr_val,
        swing_low=swing_low,
        swing_high=swing_high,
    )

    scored = score_signal(
        side=event["type"],
        long_sma_direction=slope["long_sma_direction"],
        price_above_long_sma=price_ctx["price_above_long_sma"],
        volume_confirmation=vol["confirmation"],
        rsi_status=rsi_status,
        market_trend=market_trend,
        sector_trend=sector_info.get("trend", "UNAVAILABLE"),
        extension_status=ext,
        risk_reward_ratio=rr.get("ratio"),
    )

    spread = ind.sma_spread_pct(short_val, long_val)

    return {
        "close": round(close, 2),
        "crossover": {
            "type": event["type"],
            "date": crossover_date.isoformat(),
            "days_since": max(days_since, 0),
        },
        "sma": {
            "short_period": short_sma,
            "short_value": round(short_val, 2),
            "long_period": long_sma,
            "long_value": round(long_val, 2),
            "spread_pct": spread,
            "long_sma_slope_pct": slope["long_sma_slope_pct"],
            "long_sma_direction": slope["long_sma_direction"],
        },
        "price_context": {
            "above_long_sma": price_ctx["price_above_long_sma"],
            "distance_from_long_sma_pct": price_ctx["price_distance_from_long_sma_pct"],
            "extension_status": ext,
        },
        "volume": {
            "current": vol["current"],
            "average_20": vol["average_20"],
            "ratio": vol["ratio"],
            "confirmation": vol["confirmation"],
        },
        "momentum": {
            "rsi_14": round(rsi_val, 2) if rsi_val is not None else None,
            "status": rsi_status,
        },
        "volatility": {
            "atr_14": round(atr_val, 2) if atr_val is not None else None,
            "atr_pct": atr_pct,
        },
        "market": {"trend": market_trend},
        "sector": {
            "name": sector_info.get("name"),
            "trend": sector_info.get("trend", "UNAVAILABLE"),
            "available": bool(sector_info.get("available")),
        },
        "risk_reward": rr,
        "signal": {
            "score": scored["score"],
            "classification": scored["classification"],
            "summary": scored["summary"],
        },
        "score_breakdown": scored["score_breakdown"],
        # Backward-compatible flat fields
        "crossover_type": "Bullish" if event["type"] == "BULLISH" else "Bearish",
        "crossover_date": crossover_date.isoformat(),
        "sma_short": round(short_val, 2),
        "sma_long": round(long_val, 2),
    }


def run_sma_crossover_scan(
    short_sma: int = 6,
    long_sma: int = 30,
    lookback_days: int = 400,
    max_stocks: int = 100,
    rsi_period: int = 14,
    volume_period: int = 20,
    atr_period: int = 14,
    slope_lookback: int = 5,
    include_market_context: bool = True,
    include_sector_context: bool = True,
) -> dict[str, Any]:
    """Scan Nifty 100 for scored SMA crossover research signals."""
    scan_started = datetime.now()
    logger.info(
        "scan_started short=%s long=%s lookback=%s max_stocks=%s",
        short_sma,
        long_sma,
        lookback_days,
        max_stocks,
    )

    if short_sma < 2:
        raise ValueError("Short SMA must be > 1.")
    if long_sma <= short_sma:
        raise ValueError("Long SMA must be greater than Short SMA.")
    if lookback_days < long_sma + slope_lookback + 20:
        raise ValueError(
            f"Lookback Days should be at least {long_sma + slope_lookback + 20} "
            f"for SMA {long_sma} and slope lookback {slope_lookback}."
        )
    if max_stocks < 1 or max_stocks > 200:
        raise ValueError("Max Stocks must be between 1 and 200.")
    if rsi_period < 2 or atr_period < 2 or volume_period < 2 or slope_lookback < 1:
        raise ValueError("Invalid indicator periods.")

    kite = kite_session.get_kite()

    universe = download_scan_universe(max_stocks)
    universe_source = universe.attrs.get("source", "NIFTY")
    stocks_requested = min(max_stocks, len(universe))
    if stocks_requested < max_stocks:
        logger.warning(
            "Requested %s stocks but universe %s only has %s names; scanning %s.",
            max_stocks,
            universe_source,
            len(universe),
            stocks_requested,
        )

    selected = universe.head(stocks_requested)
    symbols = selected["Symbol"].tolist()
    company_map = dict(zip(selected["Symbol"], selected["Company"]))

    token_map = map_symbols_to_tokens(kite, symbols)
    # Scan exactly the mapped symbols from the requested slice (missing tokens are skipped with reason)
    mapped_symbols = [s for s in symbols if s in token_map]
    unmapped = [s for s in symbols if s not in token_map]
    for symbol in unmapped:
        logger.warning("Instrument mapping unavailable for %s", symbol)

    market_cache = MarketContextCache(
        kite=kite,
        lookback_days=lookback_days,
        long_sma=long_sma,
        slope_lookback=slope_lookback,
    )

    if include_market_context:
        market_context = market_cache.nifty_context()
        market_trend = market_context.get("trend", "UNAVAILABLE")
    else:
        market_context = {
            "index": "NIFTY 50",
            "trend": "UNAVAILABLE",
            "available": False,
        }
        market_trend = "UNAVAILABLE"

    rows: list[dict[str, Any]] = []
    scanned = 0
    errors = 0
    failure_reasons: list[dict[str, str]] = []

    for symbol in unmapped:
        failure_reasons.append({"ticker": symbol, "reason": "Instrument mapping unavailable"})

    # Preserve CSV order and attempt exactly the requested slice
    for symbol in mapped_symbols:
        token = token_map[symbol]
        scanned += 1
        try:
            hist = fetch_daily_history(kite, token, lookback_days)
            if hist.empty:
                failure_reasons.append({"ticker": symbol, "reason": "No historical candles"})
                continue

            if include_sector_context:
                sector_info = market_cache.sector_context(symbol)
            else:
                sector_info = {"name": None, "trend": "UNAVAILABLE", "available": False}

            analyzed = analyze_stock_history(
                hist,
                short_sma=short_sma,
                long_sma=long_sma,
                rsi_period=rsi_period,
                volume_period=volume_period,
                atr_period=atr_period,
                slope_lookback=slope_lookback,
                market_trend=market_trend,
                sector_info=sector_info,
            )
            if analyzed is None:
                continue

            analyzed["ticker"] = symbol
            analyzed["company"] = company_map.get(symbol, symbol)
            rows.append(analyzed)
        except Exception as exc:
            errors += 1
            logger.warning("kite_errors / indicator_errors for %s: %s", symbol, exc)
            failure_reasons.append({"ticker": symbol, "reason": str(exc)})

        time.sleep(KITE_SLEEP_SECONDS)

    # Default ranking: score DESC, then crossover date DESC
    def sort_key(r: dict[str, Any]) -> tuple:
        return (
            -int(r.get("signal", {}).get("score", 0)),
            r.get("crossover", {}).get("date", ""),
            r.get("ticker", ""),
        )

    rows.sort(key=sort_key)

    signals: list[dict[str, Any]] = []
    for rank, row in enumerate(rows, start=1):
        item = dict(row)
        item["rank"] = rank
        signals.append(item)

    def count_class(prefix: str) -> int:
        return sum(
            1
            for s in signals
            if str(s.get("signal", {}).get("classification", "")).startswith(prefix)
        )

    bullish = sum(1 for s in signals if s.get("crossover", {}).get("type") == "BULLISH")
    bearish = sum(1 for s in signals if s.get("crossover", {}).get("type") == "BEARISH")
    scores = [int(s.get("signal", {}).get("score", 0)) for s in signals]
    avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0

    scan_completed = datetime.now()
    duration = (scan_completed - scan_started).total_seconds()
    logger.info(
        "scan_completed duration=%.1fs requested=%s scanned=%s found=%s failed=%s",
        duration,
        stocks_requested,
        scanned,
        len(signals),
        errors,
    )

    return {
        "short_sma": short_sma,
        "long_sma": long_sma,
        "lookback_days": lookback_days,
        "max_stocks": max_stocks,
        "rsi_period": rsi_period,
        "volume_period": volume_period,
        "atr_period": atr_period,
        "slope_lookback": slope_lookback,
        "scanned": scanned,
        "signals_found": len(signals),
        "errors": errors,
        "scan_summary": {
            "scan_time": scan_completed.isoformat(timespec="seconds"),
            "scan_duration_seconds": round(duration, 2),
            "universe": universe_source,
            "stocks_requested": stocks_requested,
            "stocks_scanned": scanned,
            "stocks_unmapped": len(unmapped),
            "stocks_failed": errors + len(unmapped),
            "bullish": bullish,
            "bearish": bearish,
            "strong_signals": count_class("STRONG"),
            "good_signals": count_class("GOOD"),
            "moderate_signals": count_class("MODERATE"),
            "weak_signals": count_class("WEAK") + count_class("AVOID"),
            "average_score": avg_score,
        },
        "market_context": market_context,
        "signals": signals,
        "failures": failure_reasons[:25],
        "disclaimer": (
            "This dashboard provides quantitative market-research signals based on "
            "historical market data and configurable trading rules. Signals, scores, "
            "stop references and targets are informational and are not guarantees of "
            "future performance or investment advice."
        ),
    }
