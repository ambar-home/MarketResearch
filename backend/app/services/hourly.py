"""
Hourly research scan. Separate from the daily SMA 6/30 strategy.

This does not place orders and does not output a true probability.
"Most aligned view" means the intraday rules agree. Measure it with the paper journal.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import requests

from app.config import settings
from app.services.kite_session import kite_session
from app.services.research_layer import fetch_research
from app.services.sma_scanner import map_symbols_to_tokens
from app.services.transaction_costs import estimate_round_trip_costs

logger = logging.getLogger(__name__)

MIN_AVG_VOLUME = 20_000
MAX_SPREAD_BPS = 15.0
MAX_ATR_PCT = 2.5
MIN_ATR_PCT = 0.05
EXTENSION_PCT = 0.8
PAPER_CAPITAL = 100_000.0
MAX_LOSS_PCT = 0.25
MAX_LOSS_RUPEES = PAPER_CAPITAL * MAX_LOSS_PCT / 100.0


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def session_vwap(df: pd.DataFrame) -> float | None:
    today = df["date"].dt.date == df["date"].dt.date.iloc[-1]
    window = df.loc[today]
    if window.empty or "volume" not in window:
        return None
    typical = (window["high"] + window["low"] + window["close"]) / 3.0
    vol = window["volume"].astype(float)
    if float(vol.sum()) <= 0:
        return None
    return float((typical * vol).sum() / vol.sum())


def atr_percent(df: pd.DataFrame, period: int = 14) -> float | None:
    if len(df) < period + 2:
        return None
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [
            (df["high"] - df["low"]).abs(),
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = float(tr.tail(period).mean())
    close = float(df["close"].iloc[-1])
    if close <= 0:
        return None
    return atr / close * 100.0


def hourly_bias(df: pd.DataFrame) -> dict[str, Any]:
    """Intraday EMA 9/21 plus session VWAP. Not the daily SMA 6/30 signal."""
    if len(df) < 30:
        return {"direction": "SKIP", "reason": "Not enough intraday bars"}
    close = float(df["close"].iloc[-1])
    ema9 = float(ema(df["close"], 9).iloc[-1])
    ema21 = float(ema(df["close"], 21).iloc[-1])
    vwap = session_vwap(df)
    if vwap is None or ema9 <= 0:
        return {"direction": "SKIP", "reason": "VWAP or EMA unavailable"}
    dist = (close - ema9) / ema9 * 100.0
    if abs(dist) >= EXTENSION_PCT:
        return {
            "direction": "SKIP",
            "reason": "Price is already extended versus the fast intraday average. Do not chase.",
            "close": round(close, 2),
            "ema9": round(ema9, 2),
            "ema21": round(ema21, 2),
            "vwap": round(vwap, 2),
        }
    if close > vwap and ema9 > ema21:
        direction = "UP"
    elif close < vwap and ema9 < ema21:
        direction = "DOWN"
    else:
        direction = "SKIP"
    return {
        "direction": direction,
        "reason": "Intraday EMA 9/21 and session VWAP agree" if direction != "SKIP" else "Intraday rules do not agree",
        "close": round(close, 2),
        "ema9": round(ema9, 2),
        "ema21": round(ema21, 2),
        "vwap": round(vwap, 2),
        "distance_from_fast_avg_pct": round(dist, 3),
    }


def paper_size(close: float, atr_pct: float | None) -> dict[str, Any]:
    if close <= 0 or not atr_pct or atr_pct <= 0:
        return {"shares": 0, "max_loss": MAX_LOSS_RUPEES, "reason": "Cannot size without volatility"}
    stop_distance = close * (atr_pct / 100.0) * 1.5
    if stop_distance <= 0:
        return {"shares": 0, "max_loss": MAX_LOSS_RUPEES, "reason": "Stop distance is zero"}
    shares = int(MAX_LOSS_RUPEES // stop_distance)
    return {
        "shares": max(shares, 0),
        "max_loss": round(MAX_LOSS_RUPEES, 2),
        "stop_distance": round(stop_distance, 2),
        "reason": f"Paper size so a 1.5x ATR move risks about ₹{MAX_LOSS_RUPEES:.0f} ({MAX_LOSS_PCT}% of ₹{PAPER_CAPITAL:.0f}).",
    }


def covers_costs(close: float, shares: int, atr_pct: float | None) -> dict[str, Any]:
    if shares <= 0 or close <= 0 or not atr_pct:
        return {"ok": False, "reason": "No paper size, so the hourly idea is not testable"}
    slip = settings.costs.slippage_bps
    exit_px = close * (1 + atr_pct / 100.0)
    costs = estimate_round_trip_costs(close, exit_px, shares)
    cost_pct = costs["total_cost"] / (close * shares) * 100.0
    slip_pct = (slip * 2) / 100.0
    hurdle = cost_pct + slip_pct
    ok = atr_pct > hurdle
    return {
        "ok": ok,
        "cost_pct": round(cost_pct, 3),
        "slippage_round_trip_pct": round(slip_pct, 3),
        "atr_pct": round(atr_pct, 3),
        "reason": (
            "Expected intraday range covers costs and slippage"
            if ok
            else "Expected move is smaller than costs plus slippage. Treat as a no-trade."
        ),
    }


def _openai_key() -> str:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if key:
        return key
    for path in (
        os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env"),
        os.path.join(os.path.dirname(__file__), "..", "..", ".env"),
    ):
        if not os.path.exists(path):
            continue
        for line in open(path, encoding="utf-8"):
            if line.startswith("OPENAI_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"')
    return ""


def summarize_headlines(headlines: list[str], keyword_tag: str) -> dict[str, Any]:
    """
    Optional LLM summary of headlines already fetched.
    It is not allowed to supply a price, RSI, or score.
    """
    if not headlines:
        return {"summary": "No headlines fetched.", "used_llm": False}
    api_key = _openai_key()
    if not api_key:
        return {
            "summary": f"Keyword tag is {keyword_tag}. No LLM key set, so headlines were not rewritten.",
            "used_llm": False,
        }
    prompt = (
        "Summarize these headlines in two short sentences. "
        "Do not invent prices, indicators, RSI, or scores. "
        "If the news is unclear, say so.\n\n"
        + "\n".join(f"- {title}" for title in headlines[:5])
    )
    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
                "temperature": 0,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=20,
        )
        response.raise_for_status()
        text = response.json()["choices"][0]["message"]["content"].strip()
        return {"summary": text, "used_llm": True}
    except Exception as exc:
        logger.info("headline summary failed: %s", exc)
        return {
            "summary": f"Keyword tag is {keyword_tag}. LLM summary failed, so it was not used.",
            "used_llm": False,
        }


def _quote_symbol(symbol: str) -> str:
    return f"NSE:{symbol}"


def _spread_bps(quote: dict[str, Any]) -> float | None:
    depth = quote.get("depth") or {}
    buys = depth.get("buy") or []
    sells = depth.get("sell") or []
    if not buys or not sells:
        return None
    bid = float(buys[0].get("price") or 0)
    ask = float(sells[0].get("price") or 0)
    if bid <= 0 or ask <= 0 or ask < bid:
        return None
    mid = (bid + ask) / 2.0
    return (ask - bid) / mid * 10_000.0


def _is_stale(quote: dict[str, Any]) -> bool:
    last = quote.get("last_trade_time")
    if last is None:
        return True
    if isinstance(last, str):
        try:
            last = datetime.fromisoformat(last)
        except ValueError:
            return True
    if getattr(last, "tzinfo", None) is not None:
        last = last.replace(tzinfo=None)
    return datetime.now() - last > timedelta(minutes=20)


def fetch_intraday(kite: Any, token: int, interval: str) -> pd.DataFrame:
    to_date = datetime.now()
    from_date = to_date - timedelta(days=5)
    candles = kite.historical_data(token, from_date, to_date, interval)
    if not candles:
        return pd.DataFrame()
    frame = pd.DataFrame(candles)
    frame["date"] = pd.to_datetime(frame["date"]).dt.tz_localize(None)
    return frame.sort_values("date").reset_index(drop=True)


def index_bias(kite: Any, interval: str, index_name: str = "NIFTY 50") -> dict[str, Any]:
    instruments = kite.instruments("NSE")
    token = next(
        (
            int(row["instrument_token"])
            for row in instruments
            if row.get("segment") == "INDICES" and str(row.get("tradingsymbol", "")).upper() == index_name
        ),
        None,
    )
    if token is None:
        return {"index": index_name, "bias": "UNCLEAR", "reason": "Index token unavailable"}
    frame = fetch_intraday(kite, token, interval)
    bias = hourly_bias(frame)
    return {
        "index": index_name,
        "bias": bias.get("direction", "SKIP"),
        "close": bias.get("close"),
        "vwap": bias.get("vwap"),
        "reason": bias.get("reason"),
    }


def analyze_symbol(
    kite: Any,
    symbol: str,
    token: int,
    quote: dict[str, Any],
    interval: str,
    index_view: dict[str, Any],
) -> dict[str, Any]:
    skips: list[str] = []
    last = float(quote.get("last_price") or 0)
    if last <= 0 or _is_stale(quote):
        skips.append("Quote looks stale or halted. Skip.")
    spread = _spread_bps(quote)
    if spread is None or spread > MAX_SPREAD_BPS:
        skips.append("Spread is wide or unknown. Skip illiquid names.")

    frame = fetch_intraday(kite, token, interval)
    if frame.empty:
        skips.append("No intraday candles.")
        avg_vol = 0.0
    else:
        avg_vol = float(frame["volume"].tail(20).mean())
    if avg_vol < MIN_AVG_VOLUME:
        skips.append("Average volume is too low.")

    atr_pct = atr_percent(frame) if not frame.empty else None
    if atr_pct is None or atr_pct < MIN_ATR_PCT or atr_pct > MAX_ATR_PCT:
        skips.append("Volatility is dead or too jumpy for a one-hour idea.")

    bias = hourly_bias(frame) if not frame.empty else {"direction": "SKIP", "reason": "No bars"}
    if bias.get("direction") == "SKIP":
        skips.append(str(bias.get("reason")))

    research = fetch_research(symbol)
    sentiment = research["sentiment"]["tag"]
    earnings = research["earnings"]
    if sentiment in {"UNCLEAR", "NEGATIVE"}:
        skips.append(f"News tag is {sentiment}. Unclear or negative means skip.")
    if earnings.get("event_risk") == "NEAR" and (earnings.get("days_until") or 99) <= 0:
        skips.append("Earnings are today. Skip the hourly idea.")
    if index_view.get("bias") in {"SKIP", "UNCLEAR"}:
        skips.append("Hourly Nifty context is unclear. Skip.")
    elif bias.get("direction") in {"UP", "DOWN"} and index_view.get("bias") not in {bias.get("direction"), "SKIP"}:
        if index_view.get("bias") in {"UP", "DOWN"} and index_view.get("bias") != bias.get("direction"):
            skips.append("Hourly stock bias conflicts with hourly Nifty bias.")

    size = paper_size(last or float(bias.get("close") or 0), atr_pct)
    cost_check = covers_costs(last or float(bias.get("close") or 0), int(size.get("shares") or 0), atr_pct)
    if not cost_check["ok"]:
        skips.append(cost_check["reason"])

    direction = "SKIP" if skips else bias.get("direction", "SKIP")
    summary = summarize_headlines(research["sentiment"].get("headlines") or [], sentiment)
    aligned = direction in {"UP", "DOWN"}
    return {
        "symbol": symbol,
        "interval": interval,
        "most_aligned_view": direction,
        "is_actionable": aligned,
        "why": skips[0] if skips else bias.get("reason"),
        "skip_reasons": skips,
        "price": round(last, 2) if last else bias.get("close"),
        "intraday": bias,
        "spread_bps": round(spread, 2) if spread is not None else None,
        "avg_volume_20": int(avg_vol),
        "atr_pct": round(atr_pct, 3) if atr_pct is not None else None,
        "news": {
            "tag": sentiment,
            "headlines": research["sentiment"].get("headlines") or [],
            "summary": summary["summary"],
            "used_llm": summary["used_llm"],
        },
        "earnings": earnings,
        "index_hour": index_view,
        "paper": {
            "shares": size.get("shares", 0) if aligned else 0,
            "max_loss": MAX_LOSS_RUPEES,
            "size_reason": size.get("reason"),
            "costs": cost_check,
        },
        "measure": "Record this view, then check the actual move after 15, 30, and 60 minutes. Do not treat the label as a probability.",
    }


def run_hourly_scan(interval: str = "5minute", source: str = "portfolio", max_stocks: int = 15) -> dict[str, Any]:
    if interval not in {"5minute", "15minute"}:
        raise ValueError("Interval must be 5minute or 15minute. This is not the daily strategy.")
    if max_stocks < 1 or max_stocks > 30:
        raise ValueError("Hourly scan is limited to 30 liquid names so the API is not hammered.")

    kite = kite_session.get_kite()
    if source == "portfolio":
        holdings = kite_session.get_portfolio()["holdings"]
        symbols = [row["symbol"] for row in holdings if row.get("symbol")][:max_stocks]
        source_label = "Portfolio holdings"
    else:
        from app.services.sma_scanner import download_nifty100

        symbols = download_nifty100()["Symbol"].head(max_stocks).tolist()
        source_label = "Nifty liquid shortlist"

    if not symbols:
        return {
            "interval": interval,
            "source": source_label,
            "calls": [],
            "best": None,
            "note": "No symbols to scan. Add holdings or choose the Nifty shortlist.",
        }

    tokens = map_symbols_to_tokens(kite, symbols)
    quotes = kite.quote([_quote_symbol(symbol) for symbol in symbols if symbol in tokens])
    ranked = []
    for symbol in symbols:
        quote = quotes.get(_quote_symbol(symbol)) or {}
        volume = float(quote.get("volume") or 0)
        ranked.append((volume, symbol))
    ranked.sort(reverse=True)
    selected = [symbol for _, symbol in ranked if symbol in tokens][:max_stocks]

    index_view = index_bias(kite, interval)
    calls = []
    for symbol in selected:
        try:
            calls.append(
                analyze_symbol(
                    kite,
                    symbol,
                    tokens[symbol],
                    quotes.get(_quote_symbol(symbol)) or {},
                    interval,
                    index_view,
                )
            )
        except Exception as exc:
            logger.warning("hourly scan failed for %s: %s", symbol, exc)
            calls.append(
                {
                    "symbol": symbol,
                    "interval": interval,
                    "most_aligned_view": "SKIP",
                    "is_actionable": False,
                    "why": f"Scan error: {exc}",
                    "skip_reasons": [str(exc)],
                }
            )

    actionable = [row for row in calls if row.get("is_actionable")]
    best = actionable[0] if actionable else None
    return {
        "interval": interval,
        "source": source_label,
        "separated_from_daily": "Daily SMA 6/30 is not used here.",
        "index_hour": index_view,
        "calls": calls,
        "best": best,
        "disclaimer": (
            "Most aligned view is a rule label, not the probability the price will move. "
            "Check 15, 30, and 60 minute paper results before trusting it."
        ),
    }
