"""SMA crossover signals endpoints."""

from fastapi import APIRouter, HTTPException

from app.schemas import SmaCrossoverRequest, SmaCrossoverResponse
from app.services.kite_session import kite_session
from app.services.sma_scanner import run_sma_crossover_scan

router = APIRouter(prefix="/api/signals", tags=["signals"])


@router.post("/sma-crossover", response_model=SmaCrossoverResponse)
def sma_crossover(body: SmaCrossoverRequest) -> SmaCrossoverResponse:
    if not kite_session.is_authenticated:
        raise HTTPException(status_code=401, detail="Not authenticated. Please log in.")

    try:
        result = run_sma_crossover_scan(
            short_sma=body.short_sma,
            long_sma=body.long_sma,
            lookback_days=body.lookback_days,
            max_stocks=body.max_stocks,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Scanner failed: {exc}") from exc

    return SmaCrossoverResponse(**result)
