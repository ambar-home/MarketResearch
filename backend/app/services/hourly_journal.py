"""Paper journal for hourly views versus later price moves."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from typing import Any

import pandas as pd

from app.config import BACKEND_DIR
from app.services.kite_session import kite_session
from app.services.sma_scanner import map_symbols_to_tokens

JOURNAL_FILE = BACKEND_DIR / "data" / "hourly_journal.json"


def _read() -> list[dict[str, Any]]:
    if not JOURNAL_FILE.exists():
        return []
    try:
        data = json.loads(JOURNAL_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _write(rows: list[dict[str, Any]]) -> None:
    JOURNAL_FILE.parent.mkdir(parents=True, exist_ok=True)
    JOURNAL_FILE.write_text(json.dumps(rows, indent=2), encoding="utf-8")


def add_hourly_journal(call: dict[str, Any]) -> dict[str, Any]:
    entry = {
        "id": str(uuid.uuid4()),
        "logged_at": datetime.now().isoformat(timespec="seconds"),
        "symbol": call.get("symbol"),
        "interval": call.get("interval"),
        "view": call.get("most_aligned_view"),
        "entry_price": call.get("price"),
        "news_tag": (call.get("news") or {}).get("tag"),
        "outcomes": {"15": None, "30": None, "60": None},
    }
    rows = _read()
    rows.insert(0, entry)
    _write(rows[:300])
    return entry


def _return_at(frame: pd.DataFrame, logged_at: datetime, minutes: int, entry: float) -> float | None:
    target = logged_at + timedelta(minutes=minutes)
    later = frame[frame["date"] >= target]
    if later.empty or entry <= 0:
        return None
    price = float(later.iloc[0]["close"])
    return round((price / entry - 1.0) * 100.0, 3)


def check_outcomes() -> dict[str, Any]:
    rows = _read()
    if not rows:
        return {"entries": [], "stats": _stats([])}
    symbols = sorted({row["symbol"] for row in rows if row.get("symbol") and row.get("entry_price")})
    kite = kite_session.get_kite()
    tokens = map_symbols_to_tokens(kite, symbols)
    frames: dict[str, pd.DataFrame] = {}
    start = datetime.now() - timedelta(days=5)
    for symbol, token in tokens.items():
        candles = kite.historical_data(token, start, datetime.now(), "5minute")
        if not candles:
            continue
        frame = pd.DataFrame(candles)
        frame["date"] = pd.to_datetime(frame["date"]).dt.tz_localize(None)
        frames[symbol] = frame

    for row in rows:
        frame = frames.get(row.get("symbol"))
        entry = float(row.get("entry_price") or 0)
        if frame is None or entry <= 0:
            continue
        logged = datetime.fromisoformat(row["logged_at"])
        for label, minutes in (("15", 15), ("30", 30), ("60", 60)):
            if row["outcomes"].get(label) is None:
                row["outcomes"][label] = _return_at(frame, logged, minutes, entry)
    _write(rows)
    return {"entries": rows, "stats": _stats(rows)}


def list_hourly_journal() -> dict[str, Any]:
    rows = _read()
    return {"entries": rows, "stats": _stats(rows)}


def _stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scored = []
    for row in rows:
        move = (row.get("outcomes") or {}).get("60")
        if move is None or row.get("view") not in {"UP", "DOWN"}:
            continue
        correct = (row["view"] == "UP" and move > 0) or (row["view"] == "DOWN" and move < 0)
        scored.append({"correct": correct, "move": move, "view": row["view"]})
    hits = sum(1 for item in scored if item["correct"])
    return {
        "checked_60m": len(scored),
        "hit_rate_60m": round(hits / len(scored) * 100.0, 1) if scored else None,
        "avg_signed_move_60m": round(
            sum(item["move"] if item["view"] == "UP" else -item["move"] for item in scored) / len(scored),
            3,
        )
        if scored
        else None,
        "how_to_read": (
            "Hit rate is how often the UP/DOWN label matched the later move. "
            "It is not a probability for the next idea. Trust it only after 30+ checked rows, "
            "and only if the average move still beats costs."
        ),
    }
