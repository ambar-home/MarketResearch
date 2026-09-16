"""Hourly research routes. No live orders."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.hourly import run_hourly_scan
from app.services.hourly_journal import add_hourly_journal, check_outcomes, list_hourly_journal
from app.services.kite_session import kite_session

router = APIRouter(prefix="/api/hourly", tags=["hourly"])


class HourlyScanRequest(BaseModel):
    interval: str = Field("5minute", pattern="^(5minute|15minute)$")
    source: str = Field("portfolio", pattern="^(portfolio|nifty)$")
    max_stocks: int = Field(10, ge=1, le=30)


@router.post("/scan")
def scan(body: HourlyScanRequest) -> dict:
    if not kite_session.is_authenticated:
        raise HTTPException(status_code=401, detail="Not authenticated. Please log in.")
    try:
        return run_hourly_scan(body.interval, body.source, body.max_stocks)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Hourly scan failed: {exc}") from exc


@router.post("/journal")
def journal(call: dict) -> dict:
    if not kite_session.is_authenticated:
        raise HTTPException(status_code=401, detail="Not authenticated. Please log in.")
    if call.get("most_aligned_view") not in {"UP", "DOWN"}:
        raise HTTPException(status_code=400, detail="Only an UP or DOWN view can be journaled. Skip is not a prediction.")
    return add_hourly_journal(call)


@router.get("/journal")
def journal_list() -> dict:
    if not kite_session.is_authenticated:
        raise HTTPException(status_code=401, detail="Not authenticated. Please log in.")
    return list_hourly_journal()


@router.post("/journal/check")
def journal_check() -> dict:
    if not kite_session.is_authenticated:
        raise HTTPException(status_code=401, detail="Not authenticated. Please log in.")
    try:
        return check_outcomes()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not check outcomes: {exc}") from exc
