"""Profile endpoints — uses the saved server-side Kite session."""

from fastapi import APIRouter, HTTPException

from app.schemas import ProfileResponse
from app.services.kite_session import kite_session

router = APIRouter(prefix="/api", tags=["profile"])


@router.get("/profile", response_model=ProfileResponse)
def get_profile() -> ProfileResponse:
    if not kite_session.is_authenticated:
        raise HTTPException(status_code=401, detail="Not authenticated. Please log in.")

    try:
        data = kite_session.get_profile()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Kite API error: {exc}") from exc

    return ProfileResponse(**data)
