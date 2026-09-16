"""
Research overlay: earnings date, valuation flags, headline sentiment.

This is a confirmation layer on top of the technical scanner.
It does not calculate a price forecast and does not use an LLM.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any

import requests

from app.config import BACKEND_DIR

logger = logging.getLogger(__name__)

JOURNAL_FILE = BACKEND_DIR / "data" / "journal.json"
CACHE: dict[str, tuple[datetime, dict[str, Any]]] = {}
CACHE_MINUTES = 30

POSITIVE_WORDS = {
    "beat", "beats", "growth", "upgrade", "upgraded", "strong", "record",
    "profit", "gains", "rally", "outperform", "buy", "surge", "expands",
}
NEGATIVE_WORDS = {
    "miss", "misses", "downgrade", "downgraded", "weak", "fraud", "probe",
    "loss", "losses", "fall", "falls", "slump", "warning", "cut", "cuts",
    "default", "penalty", "sell",
}


def yahoo_symbol(ticker: str) -> str:
    return f"{ticker.strip().upper()}.NS"


def classify_headlines(headlines: list[str]) -> dict[str, Any]:
    """Simple lexicon tag. UNCLEAR when there is not enough text."""
    if len(headlines) < 2:
        return {
            "tag": "UNCLEAR",
            "positive_hits": 0,
            "negative_hits": 0,
            "reason": "Not enough headlines to tag sentiment. Skip unclear cases.",
        }

    blob = " ".join(headlines).lower()
    words = set(blob.replace(".", " ").replace(",", " ").split())
    pos = len(words & POSITIVE_WORDS)
    neg = len(words & NEGATIVE_WORDS)

    if pos == 0 and neg == 0:
        return {
            "tag": "NEUTRAL",
            "positive_hits": 0,
            "negative_hits": 0,
            "reason": "Headlines found, but no strong positive/negative keywords.",
        }
    if pos > neg:
        tag = "POSITIVE"
    elif neg > pos:
        tag = "NEGATIVE"
    else:
        tag = "NEUTRAL"
    return {
        "tag": tag,
        "positive_hits": pos,
        "negative_hits": neg,
        "reason": f"Keyword balance +{pos} / -{neg}. Headline tag only, not a forecast.",
    }


def valuation_flag(pe: float | None) -> dict[str, Any]:
    """Flag only. Cheap/expensive is not a buy/sell instruction."""
    if pe is None:
        return {"flag": "UNKNOWN", "pe": None, "reason": "PE unavailable"}
    if pe < 0:
        return {"flag": "LOSS_MAKING", "pe": pe, "reason": "Trailing PE is negative (loss-making)"}
    if pe < 15:
        return {"flag": "LOW_PE", "pe": pe, "reason": "PE below 15 — cheaper vs history is not proven here"}
    if pe <= 40:
        return {"flag": "MID_PE", "pe": pe, "reason": "PE between 15 and 40"}
    return {"flag": "HIGH_PE", "pe": pe, "reason": "PE above 40 — richer valuation, higher disappointment risk"}


def earnings_context(earnings_iso: str | None, today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    if not earnings_iso:
        return {
            "date": None,
            "days_until": None,
            "event_risk": "UNKNOWN",
            "reason": "Next earnings date unavailable",
        }
    try:
        earnings_day = date.fromisoformat(earnings_iso[:10])
    except ValueError:
        return {
            "date": None,
            "days_until": None,
            "event_risk": "UNKNOWN",
            "reason": "Could not parse earnings date",
        }
    days = (earnings_day - today).days
    if 0 <= days <= 7:
        risk = "NEAR"
    elif days < 0:
        risk = "RECENT"
    else:
        risk = "NOT_NEAR"
    return {
        "date": earnings_day.isoformat(),
        "days_until": days,
        "event_risk": risk,
        "reason": (
            "Earnings are within 7 days — wait or size smaller."
            if risk == "NEAR"
            else "Earnings timing noted for context only."
        ),
    }


def careful_decision(
    *,
    score: int,
    extension: str,
    volume: str,
    side: str,
    long_sma_direction: str,
    sentiment: str,
    event_risk: str,
) -> dict[str, Any]:
    """
    Human-in-the-loop gate.
    SKIP means do not treat as an actionable research candidate.
    """
    reasons: list[str] = []
    aligned = (side == "BULLISH" and long_sma_direction == "RISING") or (
        side == "BEARISH" and long_sma_direction == "FALLING"
    )

    if score < 50:
        reasons.append("Score below 50")
    if extension == "EXTENDED":
        reasons.append("Price looks extended vs short SMA")
    if volume == "WEAK":
        reasons.append("Volume is weak")
    if not aligned:
        reasons.append("Long SMA slope does not support the crossover side")
    if sentiment == "NEGATIVE":
        reasons.append("Headline sentiment is negative")
    if sentiment == "UNCLEAR":
        reasons.append("Sentiment is unclear — skip rather than guess")
    if event_risk == "NEAR":
        reasons.append("Earnings are near — event risk")

    hard_skip = (
        score < 50
        or extension == "EXTENDED"
        or volume == "WEAK"
        or sentiment in {"NEGATIVE", "UNCLEAR"}
        or event_risk == "NEAR"
    )
    if hard_skip:
        return {
            "action": "SKIP",
            "reasons": reasons or ["Setup is not clear enough"],
            "size_hint": "No new risk. If already interested, wait.",
        }

    if score >= 70 and extension == "NORMAL" and volume == "STRONG" and sentiment == "POSITIVE" and aligned:
        return {
            "action": "RESEARCH_CANDIDATE",
            "reasons": ["Score, trend, volume, and headline tag agree. Still confirm on the chart."],
            "size_hint": "If you act, size small. This is not a forecast.",
        }

    return {
        "action": "WATCH",
        "reasons": reasons or ["Mixed confirmation. Keep on a watchlist and recheck."],
        "size_hint": "Do not size up. Skip if anything still feels unclear.",
    }


def _get_json(url: str) -> dict[str, Any] | None:
    try:
        response = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 MarketResearch research layer"},
            timeout=12,
        )
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else None
    except Exception as exc:
        logger.info("research fetch failed: %s", exc)
        return None


def fetch_research(ticker: str) -> dict[str, Any]:
    key = ticker.strip().upper()
    cached = CACHE.get(key)
    if cached and (datetime.now() - cached[0]).total_seconds() < CACHE_MINUTES * 60:
        return cached[1]

    symbol = yahoo_symbol(key)
    summary = _get_json(
        "https://query1.finance.yahoo.com/v10/finance/quoteSummary/"
        f"{symbol}?modules=calendarEvents,summaryDetail,defaultKeyStatistics"
    )
    search = _get_json(
        "https://query1.finance.yahoo.com/v1/finance/search"
        f"?q={symbol}&quotesCount=0&newsCount=6"
    )

    pe = None
    earnings_iso = None
    headlines: list[str] = []
    if summary:
        result = ((summary.get("quoteSummary") or {}).get("result") or [None])[0] or {}
        detail = result.get("summaryDetail") or {}
        pe_raw = (detail.get("trailingPE") or {}).get("raw")
        if isinstance(pe_raw, (int, float)):
            pe = round(float(pe_raw), 2)
        earnings = ((result.get("calendarEvents") or {}).get("earnings") or {})
        dates = earnings.get("earningsDate") or []
        if dates and isinstance(dates[0], dict) and dates[0].get("fmt"):
            earnings_iso = str(dates[0]["fmt"])
    if search:
        for item in search.get("news") or []:
            title = item.get("title")
            if title:
                headlines.append(str(title))

    sentiment = classify_headlines(headlines)
    valuation = valuation_flag(pe)
    earnings = earnings_context(earnings_iso)
    payload = {
        "ticker": key,
        "source": "Yahoo Finance public quote/news",
        "valuation": valuation,
        "earnings": earnings,
        "sentiment": {
            **sentiment,
            "headlines": headlines[:5],
        },
        "note": (
            "Valuation and sentiment are context flags. They do not predict the next move. "
            "Headline tags are keyword-based and can miss sarcasm or important nuance."
        ),
    }
    CACHE[key] = (datetime.now(), payload)
    return payload


def _read_journal() -> list[dict[str, Any]]:
    if not JOURNAL_FILE.exists():
        return []
    try:
        data = json.loads(JOURNAL_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _write_journal(rows: list[dict[str, Any]]) -> None:
    JOURNAL_FILE.parent.mkdir(parents=True, exist_ok=True)
    JOURNAL_FILE.write_text(json.dumps(rows, indent=2), encoding="utf-8")


def add_journal_entry(body: dict[str, Any]) -> dict[str, Any]:
    rows = _read_journal()
    entry = {
        "id": str(uuid.uuid4()),
        "logged_at": datetime.now().isoformat(timespec="seconds"),
        "ticker": str(body["ticker"]).upper(),
        "score": int(body.get("score") or 0),
        "classification": body.get("classification"),
        "sentiment": body.get("sentiment") or "UNCLEAR",
        "valuation_flag": body.get("valuation_flag"),
        "decision": body.get("decision") or "WATCH",
        "notes": body.get("notes") or "",
        "outcome_return_pct": body.get("outcome_return_pct"),
    }
    rows.insert(0, entry)
    _write_journal(rows[:500])
    return entry


def update_journal_outcome(entry_id: str, outcome_return_pct: float) -> dict[str, Any] | None:
    rows = _read_journal()
    for row in rows:
        if row.get("id") == entry_id:
            row["outcome_return_pct"] = outcome_return_pct
            row["reviewed_at"] = datetime.now().isoformat(timespec="seconds")
            _write_journal(rows)
            return row
    return None


def list_journal() -> list[dict[str, Any]]:
    return _read_journal()


def _avg(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def analyze_journal() -> dict[str, Any]:
    rows = [r for r in _read_journal() if r.get("outcome_return_pct") is not None]
    high_pos = [
        float(r["outcome_return_pct"])
        for r in rows
        if int(r.get("score") or 0) >= 70 and r.get("sentiment") == "POSITIVE"
    ]
    high_other = [
        float(r["outcome_return_pct"])
        for r in rows
        if int(r.get("score") or 0) >= 70 and r.get("sentiment") != "POSITIVE"
    ]
    by_sentiment: dict[str, list[float]] = {}
    for row in rows:
        by_sentiment.setdefault(str(row.get("sentiment") or "UNCLEAR"), []).append(
            float(row["outcome_return_pct"])
        )

    compared = high_pos and high_other
    winner = None
    if compared:
        winner = (
            "HIGH_SCORE_POSITIVE_SENTIMENT"
            if (_avg(high_pos) or 0) > (_avg(high_other) or 0)
            else "HIGH_SCORE_WITHOUT_POSITIVE_SENTIMENT"
        )

    return {
        "logged_with_outcome": len(rows),
        "high_score_positive_avg_return": _avg(high_pos),
        "high_score_positive_count": len(high_pos),
        "high_score_other_avg_return": _avg(high_other),
        "high_score_other_count": len(high_other),
        "by_sentiment": {
            key: {"count": len(vals), "avg_return_pct": _avg(vals)} for key, vals in by_sentiment.items()
        },
        "comparison": winner,
        "how_to_read": (
            "This compares your journaled outcomes, not a market backtest. "
            "A higher average is evidence only after enough samples (aim for 30+). "
            "One winning headline does not prove the method."
        ),
    }
