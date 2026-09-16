"""Unit tests for deterministic indicators."""

from __future__ import annotations

import pandas as pd

from app.services import indicators as ind


def test_sma_known_values():
    closes = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    result = ind.sma(closes, 3)
    assert pd.isna(result.iloc[1])
    assert result.iloc[2] == 2.0
    assert result.iloc[5] == 5.0


def test_sma_spread_pct():
    assert ind.sma_spread_pct(1050, 1000) == 5.0
    assert ind.sma_spread_pct(1002, 1000) == 0.2
    assert ind.sma_spread_pct(1000, 0) is None


def test_crossover_bullish_bearish_none():
    # Construct short crossing above long
    short = pd.Series([1.0, 1.0, 2.0, 3.0, 4.0])
    long = pd.Series([2.0, 2.0, 2.0, 2.0, 2.0])
    event = ind.detect_crossover(short, long)
    assert event is not None
    assert event["type"] == "BULLISH"

    short_b = pd.Series([3.0, 3.0, 2.0, 1.0, 0.5])
    long_b = pd.Series([2.0, 2.0, 2.0, 2.0, 2.0])
    event_b = ind.detect_crossover(short_b, long_b)
    assert event_b is not None
    assert event_b["type"] == "BEARISH"

    flat_s = pd.Series([1.0, 1.1, 1.2, 1.3])
    flat_l = pd.Series([2.0, 2.0, 2.0, 2.0])
    assert ind.detect_crossover(flat_s, flat_l) is None


def test_long_sma_slope_direction():
    rising = pd.Series([100.0] * 5 + [101.0, 102.0, 103.0, 104.0, 105.0])
    out = ind.long_sma_slope(rising, lookback=5, rising_pct=0.15, falling_pct=-0.15)
    assert out["long_sma_direction"] == "RISING"

    falling = pd.Series([105.0, 104.0, 103.0, 102.0, 101.0, 100.0, 99.0, 98.0, 97.0, 96.0])
    out_f = ind.long_sma_slope(falling, lookback=5, rising_pct=0.15, falling_pct=-0.15)
    assert out_f["long_sma_direction"] == "FALLING"

    flat = pd.Series([100.0] * 12)
    out_flat = ind.long_sma_slope(flat, lookback=5, rising_pct=0.15, falling_pct=-0.15)
    assert out_flat["long_sma_direction"] == "FLAT"


def test_volume_ratio():
    vols = pd.Series([100] * 20 + [180])
    out = ind.volume_metrics(vols, period=20, strong_ratio=1.5, weak_ratio=1.0)
    assert out["ratio"] == 1.8
    assert out["confirmation"] == "STRONG"


def test_rsi_bounds():
    # Strong uptrend → RSI near 100
    up = pd.Series([float(i) for i in range(1, 40)])
    rsi = ind.rsi_wilder(up, period=14).dropna()
    assert rsi.iloc[-1] > 70

    down = pd.Series([float(i) for i in range(40, 1, -1)])
    rsi_d = ind.rsi_wilder(down, period=14).dropna()
    assert rsi_d.iloc[-1] < 30


def test_atr_positive():
    n = 40
    close = pd.Series([100 + (i % 5) for i in range(n)], dtype="float64")
    high = close + 2
    low = close - 2
    atr = ind.atr_wilder(high, low, close, period=14).dropna()
    assert len(atr) > 0
    assert atr.iloc[-1] > 0
    assert ind.atr_pct(atr.iloc[-1], float(close.iloc[-1])) is not None


def test_extension_status():
    assert ind.extension_status(100, 100, elevated_pct=3, extended_pct=6) == "NORMAL"
    assert ind.extension_status(104, 100, elevated_pct=3, extended_pct=6) == "ELEVATED"
    assert ind.extension_status(108, 100, elevated_pct=3, extended_pct=6) == "EXTENDED"
