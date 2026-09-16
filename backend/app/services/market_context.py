"""
Market and sector context for a single scan.

Index / sector OHLC is fetched once per scan and reused for all stocks.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
from kiteconnect import KiteConnect

from app.config import NIFTY50_INDEX_NAME, settings
from app.services import indicators as ind

logger = logging.getLogger(__name__)

# Curated symbol → NSE sector index (Kite INDICES tradingsymbol).
# Only include mappings we are reasonably confident about.
# If a symbol is missing, sector confirmation is marked UNAVAILABLE.
SYMBOL_TO_SECTOR_INDEX: dict[str, str] = {
    # Banking / Financials
    "HDFCBANK": "NIFTY BANK",
    "ICICIBANK": "NIFTY BANK",
    "SBIN": "NIFTY BANK",
    "KOTAKBANK": "NIFTY BANK",
    "AXISBANK": "NIFTY BANK",
    "INDUSINDBK": "NIFTY BANK",
    "BANKBARODA": "NIFTY BANK",
    "PNB": "NIFTY BANK",
    "IDFCFIRSTB": "NIFTY BANK",
    "FEDERALBNK": "NIFTY BANK",
    "AUBANK": "NIFTY BANK",
    # IT
    "TCS": "NIFTY IT",
    "INFY": "NIFTY IT",
    "HCLTECH": "NIFTY IT",
    "WIPRO": "NIFTY IT",
    "TECHM": "NIFTY IT",
    "LTIM": "NIFTY IT",
    "PERSISTENT": "NIFTY IT",
    "COFORGE": "NIFTY IT",
    "MPHASIS": "NIFTY IT",
    # Auto
    "MARUTI": "NIFTY AUTO",
    "TATAMOTORS": "NIFTY AUTO",
    "M&M": "NIFTY AUTO",
    "BAJAJ-AUTO": "NIFTY AUTO",
    "HEROMOTOCO": "NIFTY AUTO",
    "EICHERMOT": "NIFTY AUTO",
    "TVSMOTOR": "NIFTY AUTO",
    "ASHOKLEY": "NIFTY AUTO",
    "BOSCHLTD": "NIFTY AUTO",
    # Pharma
    "SUNPHARMA": "NIFTY PHARMA",
    "DRREDDY": "NIFTY PHARMA",
    "CIPLA": "NIFTY PHARMA",
    "DIVISLAB": "NIFTY PHARMA",
    "LUPIN": "NIFTY PHARMA",
    "AUROPHARMA": "NIFTY PHARMA",
    "TORNTPHARM": "NIFTY PHARMA",
    "ALKEM": "NIFTY PHARMA",
    # FMCG
    "HINDUNILVR": "NIFTY FMCG",
    "ITC": "NIFTY FMCG",
    "NESTLEIND": "NIFTY FMCG",
    "BRITANNIA": "NIFTY FMCG",
    "DABUR": "NIFTY FMCG",
    "MARICO": "NIFTY FMCG",
    "GODREJCP": "NIFTY FMCG",
    "COLPAL": "NIFTY FMCG",
    "TATACONSUM": "NIFTY FMCG",
    "UNITDSPR": "NIFTY FMCG",
    # Metal
    "TATASTEEL": "NIFTY METAL",
    "JSWSTEEL": "NIFTY METAL",
    "HINDALCO": "NIFTY METAL",
    "VEDL": "NIFTY METAL",
    "JINDALSTEL": "NIFTY METAL",
    "NMDC": "NIFTY METAL",
    "SAIL": "NIFTY METAL",
    "HINDZINC": "NIFTY METAL",
    "NATIONALUM": "NIFTY METAL",
    # Realty
    "DLF": "NIFTY REALTY",
    "GODREJPROP": "NIFTY REALTY",
    "OBEROIRLTY": "NIFTY REALTY",
    "PRESTIGE": "NIFTY REALTY",
    "PHOENIXLTD": "NIFTY REALTY",
    # Energy / Oil-Gas
    "RELIANCE": "NIFTY ENERGY",
    "ONGC": "NIFTY ENERGY",
    "NTPC": "NIFTY ENERGY",
    "POWERGRID": "NIFTY ENERGY",
    "BPCL": "NIFTY ENERGY",
    "IOC": "NIFTY ENERGY",
    "GAIL": "NIFTY ENERGY",
    "ADANIGREEN": "NIFTY ENERGY",
    "TATAPOWER": "NIFTY ENERGY",
    "ADANIENSOL": "NIFTY ENERGY",
}


def classify_index_trend(
    close: float,
    long_sma_value: float,
    long_sma_direction: str,
) -> str:
    """Transparent rule-based index trend."""
    if pd.isna(close) or pd.isna(long_sma_value):
        return "NEUTRAL"
    if close > long_sma_value and long_sma_direction == "RISING":
        return "BULLISH"
    if close < long_sma_value and long_sma_direction == "FALLING":
        return "BEARISH"
    return "NEUTRAL"


def analyze_index_history(
    df: pd.DataFrame,
    long_sma: int,
    slope_lookback: int,
    index_name: str,
) -> dict[str, Any]:
    if df.empty or "close" not in df.columns:
        return {
            "index": index_name,
            "trend": "UNAVAILABLE",
            "close": None,
            "long_sma": None,
            "long_sma_direction": "UNKNOWN",
            "available": False,
        }

    long_series = ind.sma(df["close"], long_sma)
    slope = ind.long_sma_slope(long_series, lookback=slope_lookback)
    close = float(df["close"].iloc[-1])
    long_val = float(long_series.dropna().iloc[-1]) if long_series.dropna().size else None
    direction = slope["long_sma_direction"]
    trend = (
        classify_index_trend(close, long_val, direction)
        if long_val is not None
        else "NEUTRAL"
    )

    return {
        "index": index_name,
        "trend": trend,
        "close": round(close, 2),
        "long_sma": round(long_val, 2) if long_val is not None else None,
        "long_sma_direction": direction,
        "long_sma_slope_pct": slope["long_sma_slope_pct"],
        "available": True,
    }


class MarketContextCache:
    """Fetch and cache index histories once per scan."""

    def __init__(self, kite: KiteConnect, lookback_days: int, long_sma: int, slope_lookback: int):
        self.kite = kite
        self.lookback_days = lookback_days
        self.long_sma = long_sma
        self.slope_lookback = slope_lookback
        self._index_tokens: dict[str, int] | None = None
        self._history: dict[str, pd.DataFrame] = {}
        self._analysis: dict[str, dict[str, Any]] = {}

    def _load_index_tokens(self) -> dict[str, int]:
        if self._index_tokens is not None:
            return self._index_tokens

        instruments = self.kite.instruments("NSE")
        tokens: dict[str, int] = {}
        for row in instruments:
            if row.get("segment") != "INDICES":
                continue
            name = str(row.get("tradingsymbol") or "").strip().upper()
            if name:
                tokens[name] = int(row["instrument_token"])
        self._index_tokens = tokens
        return tokens

    def _fetch_history(self, index_name: str) -> pd.DataFrame:
        key = index_name.upper()
        if key in self._history:
            return self._history[key]

        tokens = self._load_index_tokens()
        token = tokens.get(key)
        if token is None:
            logger.warning("Index instrument not found: %s", index_name)
            self._history[key] = pd.DataFrame()
            return self._history[key]

        to_date = datetime.now().date()
        from_date = to_date - timedelta(days=self.lookback_days)
        try:
            candles = self.kite.historical_data(
                instrument_token=token,
                from_date=from_date,
                to_date=to_date,
                interval="day",
                continuous=False,
                oi=False,
            )
        except Exception as exc:
            logger.warning("Failed to fetch history for %s: %s", index_name, exc)
            self._history[key] = pd.DataFrame()
            return self._history[key]

        if not candles:
            self._history[key] = pd.DataFrame()
            return self._history[key]

        df = pd.DataFrame(candles)
        df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None).dt.normalize()
        df = df.sort_values("date").reset_index(drop=True)
        self._history[key] = df
        return df

    def get_analysis(self, index_name: str) -> dict[str, Any]:
        key = index_name.upper()
        if key in self._analysis:
            return self._analysis[key]
        df = self._fetch_history(index_name)
        analysis = analyze_index_history(df, self.long_sma, self.slope_lookback, index_name)
        self._analysis[key] = analysis
        return analysis

    def nifty_context(self) -> dict[str, Any]:
        return self.get_analysis(NIFTY50_INDEX_NAME)

    def sector_context(self, symbol: str) -> dict[str, Any]:
        sector_index = SYMBOL_TO_SECTOR_INDEX.get(symbol.upper())
        if not sector_index:
            return {
                "name": None,
                "trend": "UNAVAILABLE",
                "available": False,
                "reason": "No curated sector-index mapping for this symbol",
            }
        analysis = self.get_analysis(sector_index)
        return {
            "name": sector_index,
            "trend": analysis.get("trend", "UNAVAILABLE"),
            "close": analysis.get("close"),
            "long_sma": analysis.get("long_sma"),
            "long_sma_direction": analysis.get("long_sma_direction"),
            "available": bool(analysis.get("available")),
        }
