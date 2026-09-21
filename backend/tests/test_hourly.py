"""Unit tests for hourly rules. No broker calls."""

from datetime import datetime, timedelta

import pandas as pd

from app.services.hourly import covers_costs, hourly_bias, paper_size
from app.services.hourly_journal import _stats


def _bars(prices: list[float]) -> pd.DataFrame:
    start = datetime(2026, 9, 16, 9, 15)
    rows = []
    for i, price in enumerate(prices):
        rows.append(
            {
                "date": start + timedelta(minutes=5 * i),
                "open": price,
                "high": price + 0.2,
                "low": price - 0.2,
                "close": price,
                "volume": 50_000,
            }
        )
    return pd.DataFrame(rows)


def test_up_bias_when_trend_and_vwap_agree():
    prices = [100 + i * 0.15 for i in range(40)]
    out = hourly_bias(_bars(prices))
    assert out["direction"] == "UP"


def test_skip_when_extended():
    prices = [100] * 35 + [103, 104, 105, 106, 108]
    out = hourly_bias(_bars(prices))
    assert out["direction"] == "SKIP"


def test_cost_gate_rejects_tiny_move():
    out = covers_costs(close=100, shares=10, atr_pct=0.01)
    assert out["ok"] is False


def test_paper_size_is_small():
    sized = paper_size(100, 1.0)
    assert sized["shares"] > 0
    assert sized["shares"] * 1.5 <= 500


def test_stats_do_not_invent_hit_rate():
    stats = _stats([])
    assert stats["hit_rate_60m"] is None


def test_hourly_universe_uses_nifty_200_not_holdings(monkeypatch):
    import pandas as pd

    from app.services import hourly

    monkeypatch.setattr(
        "app.services.sma_scanner.download_nifty200",
        lambda: pd.DataFrame({"Symbol": [f"STK{i}" for i in range(200)]}),
    )
    symbols, label = hourly.hourly_universe("nifty", 200)
    assert label == "Nifty 200"
    assert len(symbols) == 200
    assert symbols[0] == "STK0"
