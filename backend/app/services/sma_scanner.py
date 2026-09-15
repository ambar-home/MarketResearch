"""
Nifty 100 SMA crossover scanner.

Uses the server-side Kite session (never exposes access_token).
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

from app.services.kite_session import kite_session

logger = logging.getLogger(__name__)

NIFTY100_CSV_URL = "https://archives.nseindia.com/content/indices/ind_nifty100list.csv"
SLEEP_SECONDS = 0.25


def download_nifty100() -> pd.DataFrame:
    """Load official Nifty 100 constituents from the Nifty Indices CSV."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/csv,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nseindia.com/",
    }

    response = requests.get(NIFTY100_CSV_URL, headers=headers, timeout=30)
    response.raise_for_status()

    nifty100 = pd.read_csv(StringIO(response.text))
    if "Symbol" not in nifty100.columns:
        raise ValueError(f"Unexpected Nifty 100 CSV columns: {list(nifty100.columns)}")

    if "Company Name" in nifty100.columns:
        nifty100 = nifty100.rename(columns={"Company Name": "Company"})
    elif "Company" not in nifty100.columns:
        nifty100["Company"] = nifty100["Symbol"]

    nifty100["Symbol"] = nifty100["Symbol"].astype(str).str.strip().str.upper()
    nifty100["Company"] = nifty100["Company"].astype(str).str.strip()
    return nifty100[["Symbol", "Company"]].copy()


def map_symbols_to_tokens(kite: KiteConnect, symbols: list[str]) -> dict[str, int]:
    """Map NSE EQ tradingsymbols to Kite instrument tokens."""
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


def find_latest_crossover(
    df: pd.DataFrame,
    short_sma: int,
    long_sma: int,
) -> dict[str, Any] | None:
    """
    Bullish: short SMA crosses above long SMA.
    Bearish: short SMA crosses below long SMA.
    Returns the most recent event only.
    """
    data = df.copy()
    short_col = f"sma_{short_sma}"
    long_col = f"sma_{long_sma}"

    data[short_col] = data["close"].rolling(window=short_sma, min_periods=short_sma).mean()
    data[long_col] = data["close"].rolling(window=long_sma, min_periods=long_sma).mean()
    data = data.dropna(subset=[short_col, long_col]).reset_index(drop=True)

    if len(data) < 2:
        return None

    prev_diff = data[short_col].shift(1) - data[long_col].shift(1)
    curr_diff = data[short_col] - data[long_col]

    bullish = (prev_diff <= 0) & (curr_diff > 0)
    bearish = (prev_diff >= 0) & (curr_diff < 0)

    events: list[dict[str, Any]] = []
    for idx in data.index[bullish]:
        row = data.loc[idx]
        events.append(
            {
                "crossover_type": "Bullish",
                "crossover_date": row["date"].date(),
                "close": round(float(row["close"]), 2),
                "sma_short": round(float(row[short_col]), 2),
                "sma_long": round(float(row[long_col]), 2),
            }
        )

    for idx in data.index[bearish]:
        row = data.loc[idx]
        events.append(
            {
                "crossover_type": "Bearish",
                "crossover_date": row["date"].date(),
                "close": round(float(row["close"]), 2),
                "sma_short": round(float(row[short_col]), 2),
                "sma_long": round(float(row[long_col]), 2),
            }
        )

    if not events:
        return None

    events.sort(key=lambda item: item["crossover_date"], reverse=True)
    return events[0]


def run_sma_crossover_scan(
    short_sma: int = 6,
    long_sma: int = 30,
    lookback_days: int = 400,
    max_stocks: int = 100,
) -> dict[str, Any]:
    """Scan Nifty 100 for SMA crossovers using the saved Kite session."""
    if short_sma >= long_sma:
        raise ValueError("Short SMA must be smaller than Long SMA.")
    if lookback_days < long_sma + 5:
        raise ValueError(f"Lookback Days should be at least {long_sma + 5} for SMA {long_sma}.")
    if max_stocks < 1:
        raise ValueError("Max Stocks must be at least 1.")

    kite = kite_session.get_kite()

    nifty100 = download_nifty100()
    nifty100 = nifty100.head(max_stocks)
    symbols = nifty100["Symbol"].tolist()
    company_map = dict(zip(nifty100["Symbol"], nifty100["Company"]))

    token_map = map_symbols_to_tokens(kite, symbols)
    rows: list[dict[str, Any]] = []
    scanned = 0
    errors = 0

    for symbol, token in token_map.items():
        scanned += 1
        try:
            hist = fetch_daily_history(kite, token, lookback_days)
            if hist.empty:
                continue

            signal = find_latest_crossover(hist, short_sma, long_sma)
            if signal is None:
                continue

            rows.append(
                {
                    "ticker": symbol,
                    "company": company_map.get(symbol, symbol),
                    "crossover_type": signal["crossover_type"],
                    "crossover_date": signal["crossover_date"],
                    "close": signal["close"],
                    "sma_short": signal["sma_short"],
                    "sma_long": signal["sma_long"],
                }
            )
        except Exception as exc:
            errors += 1
            logger.warning("Scan error for %s: %s", symbol, exc)

        time.sleep(SLEEP_SECONDS)

    rows.sort(key=lambda r: (r["crossover_date"], r["ticker"]), reverse=True)
    # Stable alphabetical within same date: re-sort properly
    rows.sort(key=lambda r: r["ticker"])
    rows.sort(key=lambda r: r["crossover_date"], reverse=True)

    signals = []
    for rank, row in enumerate(rows, start=1):
        crossover_date: date = row["crossover_date"]
        signals.append(
            {
                "rank": rank,
                "ticker": row["ticker"],
                "company": row["company"],
                "crossover_type": row["crossover_type"],
                "crossover_date": crossover_date.isoformat(),
                "close": row["close"],
                "sma_short": row["sma_short"],
                "sma_long": row["sma_long"],
            }
        )

    return {
        "short_sma": short_sma,
        "long_sma": long_sma,
        "lookback_days": lookback_days,
        "max_stocks": max_stocks,
        "scanned": scanned,
        "signals_found": len(signals),
        "errors": errors,
        "signals": signals,
    }
