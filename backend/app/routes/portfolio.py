"""Portfolio endpoints — holdings and open positions stay read-only."""

from fastapi import APIRouter, HTTPException

from app.services.kite_session import kite_session

router = APIRouter(prefix="/api", tags=["portfolio"])


@router.get("/portfolio")
def get_portfolio() -> dict:
    if not kite_session.is_authenticated:
        raise HTTPException(status_code=401, detail="Not authenticated. Please log in.")
    try:
        return kite_session.get_portfolio()
    except Exception as exc:
        message = str(exc)
        if "permission" in message.lower() or "insufficient" in message.lower():
            message = (
                "Kite denied portfolio access. Enable Holdings permission on your "
                "Kite Connect app, then log in again."
            )
        raise HTTPException(status_code=502, detail=message) from exc
