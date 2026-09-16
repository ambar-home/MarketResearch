"""
FastAPI entrypoint for MarketResearch + Zerodha Kite Connect.

Run from the backend/ folder:
  uvicorn app.main:app --reload --port 8000
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import CORS_ORIGINS
from app.routes import auth, backtest, hourly, portfolio, profile, research, signals
from app.services.kite_session import kite_session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="MarketResearch API",
    description="Zerodha Kite Connect backend. Access tokens stay on the server.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(portfolio.router)
app.include_router(signals.router)
app.include_router(backtest.router)
app.include_router(research.router)
app.include_router(hourly.router)


@app.on_event("startup")
def on_startup() -> None:
    """Reuse a saved access token during local development."""
    restored = kite_session.try_restore()
    if restored:
        logger.info("Session restored — no re-login needed.")
    else:
        logger.info("No valid saved session. Use the Login page.")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
