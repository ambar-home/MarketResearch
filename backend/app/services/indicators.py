"""
Deterministic technical indicators for OHLCV daily candles.

All functions are pure (DataFrame / Series in → values out).
No network calls. No LLM involvement.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.config import settings


def sma(series: pd.Series, period: int) -> pd.Series:
    """Simple moving average."""
    return series.rolling(window=period, min_periods=period).mean()


def sma_spread_pct(short_value: float, long_value: float) -> float | None:
    """((short - long) / long) * 100"""
    if long_value == 0 or pd.isna(short_value) or pd.isna(long_value):
        return None
    return round(((short_value - long_value) / long_value) * 100.0, 4)


def long_sma_slope(
    long_sma_series: pd.Series,
    lookback: int | None = None,
    rising_pct: float | None = None,
    falling_pct: float | None = None,
) -> dict[str, Any]:
    """
    Compare current long SMA vs long SMA N sessions ago.
    Returns slope % and RISING / FLAT / FALLING.
    """
    lookback = lookback if lookback is not None else settings.indicators.slope_lookback
    rising_pct = rising_pct if rising_pct is not None else settings.slope.rising_pct
    falling_pct = falling_pct if falling_pct is not None else settings.slope.falling_pct

    clean = long_sma_series.dropna()
    if len(clean) <= lookback:
        return {"long_sma_slope_pct": None, "long_sma_direction": "UNKNOWN"}

    current = float(clean.iloc[-1])
    previous = float(clean.iloc[-(lookback + 1)])
    if previous == 0:
        return {"long_sma_slope_pct": None, "long_sma_direction": "UNKNOWN"}

    slope = ((current - previous) / previous) * 100.0
    if slope > rising_pct:
        direction = "RISING"
    elif slope < falling_pct:
        direction = "FALLING"
    else:
        direction = "FLAT"

    return {
        "long_sma_slope_pct": round(slope, 4),
        "long_sma_direction": direction,
    }


def price_vs_long_sma(close: float, long_sma_value: float) -> dict[str, Any]:
    if long_sma_value == 0 or pd.isna(close) or pd.isna(long_sma_value):
        return {
            "price_above_long_sma": None,
            "price_distance_from_long_sma_pct": None,
        }
    dist = ((close - long_sma_value) / long_sma_value) * 100.0
    return {
        "price_above_long_sma": bool(close > long_sma_value),
        "price_distance_from_long_sma_pct": round(dist, 4),
    }


def extension_status(
    close: float,
    short_sma_value: float,
    elevated_pct: float | None = None,
    extended_pct: float | None = None,
) -> str:
    """Classify how far price has run from the short SMA."""
    elevated_pct = elevated_pct if elevated_pct is not None else settings.extension.elevated_pct
    extended_pct = extended_pct if extended_pct is not None else settings.extension.extended_pct

    if short_sma_value == 0 or pd.isna(close) or pd.isna(short_sma_value):
        return "UNKNOWN"

    dist = abs(((close - short_sma_value) / short_sma_value) * 100.0)
    if dist >= extended_pct:
        return "EXTENDED"
    if dist >= elevated_pct:
        return "ELEVATED"
    return "NORMAL"


def volume_metrics(
    volume_series: pd.Series,
    period: int | None = None,
    strong_ratio: float | None = None,
    weak_ratio: float | None = None,
) -> dict[str, Any]:
    period = period if period is not None else settings.indicators.volume_period
    strong_ratio = strong_ratio if strong_ratio is not None else settings.volume.strong_ratio
    weak_ratio = weak_ratio if weak_ratio is not None else settings.volume.weak_ratio

    clean = volume_series.dropna()
    if len(clean) < period + 1:
        return {
            "current": None,
            "average_20": None,
            "ratio": None,
            "confirmation": "UNKNOWN",
        }

    current = float(clean.iloc[-1])
    avg = float(clean.iloc[-(period + 1) : -1].mean())
    if avg <= 0:
        return {
            "current": int(current),
            "average_20": None,
            "ratio": None,
            "confirmation": "UNKNOWN",
        }

    ratio = current / avg
    if ratio >= strong_ratio:
        confirmation = "STRONG"
    elif ratio >= weak_ratio:
        confirmation = "NORMAL"
    else:
        confirmation = "WEAK"

    return {
        "current": int(round(current)),
        "average_20": int(round(avg)),
        "ratio": round(ratio, 4),
        "confirmation": confirmation,
    }


def rsi_wilder(close: pd.Series, period: int = 14) -> pd.Series:
    """
    Wilder's RSI.
    First average uses simple mean of gains/losses; then Wilder smoothing.
    """
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)

    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()

    rsi = pd.Series(index=close.index, dtype="float64")

    # Seed
    if len(close) <= period:
        return rsi

    avg_g = float(avg_gain.iloc[period])
    avg_l = float(avg_loss.iloc[period])
    if avg_l == 0:
        rsi.iloc[period] = 100.0
    else:
        rs = avg_g / avg_l
        rsi.iloc[period] = 100.0 - (100.0 / (1.0 + rs))

    for i in range(period + 1, len(close)):
        avg_g = ((avg_g * (period - 1)) + float(gain.iloc[i])) / period
        avg_l = ((avg_l * (period - 1)) + float(loss.iloc[i])) / period
        if avg_l == 0:
            rsi.iloc[i] = 100.0
        else:
            rs = avg_g / avg_l
            rsi.iloc[i] = 100.0 - (100.0 / (1.0 + rs))

    return rsi


def momentum_status(rsi_value: float | None, side: str) -> str:
    """
    Contextual RSI status for bullish or bearish research signals.
    Ranges are heuristics — configurable later via backtests.
    """
    if rsi_value is None or pd.isna(rsi_value):
        return "UNKNOWN"

    if side.upper() == "BULLISH":
        if 55 <= rsi_value <= 70:
            return "SUPPORTIVE"
        if 45 <= rsi_value < 55:
            return "NEUTRAL"
        if rsi_value > 75:
            return "EXTENDED"
        if rsi_value < 40:
            return "WEAK"
        return "NEUTRAL"

    # Bearish context
    if 30 <= rsi_value <= 45:
        return "SUPPORTIVE"
    if 45 < rsi_value <= 55:
        return "NEUTRAL"
    if rsi_value < 25:
        return "EXTENDED"
    if rsi_value > 60:
        return "WEAK"
    return "NEUTRAL"


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    prev_close = close.shift(1)
    ranges = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    )
    return ranges.max(axis=1)


def atr_wilder(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Average True Range with Wilder smoothing."""
    tr = true_range(high, low, close)
    atr = pd.Series(index=close.index, dtype="float64")
    if len(tr.dropna()) < period:
        return atr

    # First ATR = SMA of first `period` true ranges (starting at index `period`)
    seed_idx = tr.first_valid_index()
    if seed_idx is None:
        return atr

    # Use positional indexing for stability
    valid_start = tr.index.get_loc(seed_idx)
    if isinstance(valid_start, slice):
        valid_start = valid_start.start or 0

    # Find first index where we have `period` TR values
    for i in range(len(tr)):
        window = tr.iloc[max(0, i - period + 1) : i + 1]
        if window.notna().sum() >= period and i >= period:
            atr.iloc[i] = float(window.tail(period).mean())
            start_i = i
            break
    else:
        return atr

    prev = float(atr.iloc[start_i])
    for i in range(start_i + 1, len(tr)):
        if pd.isna(tr.iloc[i]):
            continue
        prev = ((prev * (period - 1)) + float(tr.iloc[i])) / period
        atr.iloc[i] = prev

    return atr


def atr_pct(atr_value: float | None, close: float | None) -> float | None:
    if atr_value is None or close is None or close == 0 or pd.isna(atr_value) or pd.isna(close):
        return None
    return round((atr_value / close) * 100.0, 4)


def detect_crossover(
    short_sma_series: pd.Series,
    long_sma_series: pd.Series,
) -> dict[str, Any] | None:
    """
    Latest SMA crossover event.
    Bullish: prev short <= prev long AND curr short > curr long
    Bearish: prev short >= prev long AND curr short < curr long
    """
    data = pd.DataFrame({"short": short_sma_series, "long": long_sma_series}).dropna()
    if len(data) < 2:
        return None

    prev_diff = data["short"].shift(1) - data["long"].shift(1)
    curr_diff = data["short"] - data["long"]

    bullish = (prev_diff <= 0) & (curr_diff > 0)
    bearish = (prev_diff >= 0) & (curr_diff < 0)

    events: list[dict[str, Any]] = []
    for idx in data.index[bullish]:
        events.append({"type": "BULLISH", "index": idx})
    for idx in data.index[bearish]:
        events.append({"type": "BEARISH", "index": idx})

    if not events:
        return None

    # Most recent by position in series
    events.sort(key=lambda e: data.index.get_loc(e["index"]))
    latest = events[-1]
    return {"type": latest["type"], "index": latest["index"]}


def latest_swing_low(low: pd.Series, lookback: int = 10) -> float | None:
    clean = low.dropna()
    if clean.empty:
        return None
    window = clean.tail(lookback)
    return float(window.min())


def latest_swing_high(high: pd.Series, lookback: int = 10) -> float | None:
    clean = high.dropna()
    if clean.empty:
        return None
    window = clean.tail(lookback)
    return float(window.max())
