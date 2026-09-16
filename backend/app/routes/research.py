"""Research overlay, journal, and outcome analysis."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.kite_session import kite_session
from app.services.research_layer import (
    add_journal_entry,
    analyze_journal,
    careful_decision,
    fetch_research,
    list_journal,
    update_journal_outcome,
)

router = APIRouter(prefix="/api/research", tags=["research"])


class ResearchQuery(BaseModel):
    score: int = 0
    extension: str = "UNKNOWN"
    volume: str = "UNKNOWN"
    side: str = "BULLISH"
    long_sma_direction: str = "UNKNOWN"


class JournalCreate(BaseModel):
    ticker: str = Field(..., min_length=1)
    score: int = 0
    classification: str | None = None
    sentiment: str | None = None
    valuation_flag: str | None = None
    decision: str | None = None
    notes: str | None = None
    outcome_return_pct: float | None = None


class OutcomeUpdate(BaseModel):
    outcome_return_pct: float


@router.get("/overlay/{ticker}")
def get_research(
    ticker: str,
    score: int = 0,
    extension: str = "UNKNOWN",
    volume: str = "UNKNOWN",
    side: str = "BULLISH",
    long_sma_direction: str = "UNKNOWN",
) -> dict:
    if not kite_session.is_authenticated:
        raise HTTPException(status_code=401, detail="Not authenticated. Please log in.")
    research = fetch_research(ticker)
    decision = careful_decision(
        score=score,
        extension=extension,
        volume=volume,
        side=side.upper(),
        long_sma_direction=long_sma_direction.upper(),
        sentiment=research["sentiment"]["tag"],
        event_risk=research["earnings"]["event_risk"],
    )
    return {**research, "decision": decision}


@router.get("/journal/list")
def journal_list() -> dict:
    if not kite_session.is_authenticated:
        raise HTTPException(status_code=401, detail="Not authenticated. Please log in.")
    return {"entries": list_journal(), "analysis": analyze_journal()}


@router.post("/journal")
def journal_create(body: JournalCreate) -> dict:
    if not kite_session.is_authenticated:
        raise HTTPException(status_code=401, detail="Not authenticated. Please log in.")
    return add_journal_entry(body.model_dump())


@router.patch("/journal/{entry_id}")
def journal_outcome(entry_id: str, body: OutcomeUpdate) -> dict:
    if not kite_session.is_authenticated:
        raise HTTPException(status_code=401, detail="Not authenticated. Please log in.")
    updated = update_journal_outcome(entry_id, body.outcome_return_pct)
    if updated is None:
        raise HTTPException(status_code=404, detail="Journal entry not found")
    return {"entry": updated, "analysis": analyze_journal()}
