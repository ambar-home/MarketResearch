"""Request / response models. Access tokens never appear in responses."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    api_key: str = Field(..., min_length=1, description="Kite API key")
    api_secret: str = Field(..., min_length=1, description="Kite API secret")
    request_token: str = Field(..., min_length=1, description="One-time request token")


class AuthStatusResponse(BaseModel):
    authenticated: bool
    user_id: str | None = None
    user_name: str | None = None


class LoginResponse(BaseModel):
    ok: bool
    message: str
    user_id: str | None = None
    user_name: str | None = None


class ProfileResponse(BaseModel):
    user_name: str
    user_id: str
    products: list[str]
    exchanges: list[str]
    email: str | None = None
    broker: str | None = None


class ErrorResponse(BaseModel):
    detail: str


class SmaCrossoverRequest(BaseModel):
    short_sma: int = Field(6, ge=2, le=100)
    long_sma: int = Field(30, ge=3, le=300)
    lookback_days: int = Field(400, ge=40, le=2000)
    max_stocks: int = Field(100, ge=1, le=200)
    rsi_period: int = Field(14, ge=2, le=100)
    volume_period: int = Field(20, ge=2, le=100)
    atr_period: int = Field(14, ge=2, le=100)
    slope_lookback: int = Field(5, ge=1, le=60)
    include_market_context: bool = True
    include_sector_context: bool = True


class ScoreBreakdownItem(BaseModel):
    factor: str
    score: float
    max_score: int
    status: str
    reason: str


class SmaSignalRow(BaseModel):
    """Enhanced signal row with backward-compatible flat fields."""

    rank: int
    ticker: str
    company: str
    close: float

    # Nested research payload
    crossover: dict[str, Any] | None = None
    sma: dict[str, Any] | None = None
    price_context: dict[str, Any] | None = None
    volume: dict[str, Any] | None = None
    momentum: dict[str, Any] | None = None
    volatility: dict[str, Any] | None = None
    market: dict[str, Any] | None = None
    sector: dict[str, Any] | None = None
    risk_reward: dict[str, Any] | None = None
    signal: dict[str, Any] | None = None
    score_breakdown: list[ScoreBreakdownItem] | list[dict[str, Any]] = Field(default_factory=list)

    # Backward compatible flat fields
    crossover_type: str | None = None
    crossover_date: str | None = None
    sma_short: float | None = None
    sma_long: float | None = None


class ScanSummary(BaseModel):
    scan_time: str
    scan_duration_seconds: float | None = None
    universe: str | None = None
    stocks_requested: int
    stocks_scanned: int
    stocks_unmapped: int | None = None
    stocks_failed: int
    bullish: int
    bearish: int
    strong_signals: int
    good_signals: int
    moderate_signals: int
    weak_signals: int
    average_score: float


class SmaCrossoverResponse(BaseModel):
    short_sma: int
    long_sma: int
    lookback_days: int
    max_stocks: int
    rsi_period: int | None = None
    volume_period: int | None = None
    atr_period: int | None = None
    slope_lookback: int | None = None
    scanned: int
    signals_found: int
    errors: int
    scan_summary: ScanSummary | dict[str, Any] | None = None
    market_context: dict[str, Any] | None = None
    signals: list[SmaSignalRow]
    failures: list[dict[str, str]] | None = None
    disclaimer: str | None = None


class BacktestRequest(BaseModel):
    short_sma: int = Field(6, ge=2, le=200)
    long_sma: int = Field(30, ge=3, le=400)
    start_date: str = Field(..., description="YYYY-MM-DD")
    end_date: str = Field(..., description="YYYY-MM-DD")
    initial_capital: float = Field(1_000_000, gt=0)
    transaction_costs: bool = True
    slippage_bps: float = Field(5, ge=0, le=100)
    max_stocks: int = Field(15, ge=1, le=200, description="Max stocks to include in backtest")
    compare_combos: bool = False


class BacktestResponse(BaseModel):
    params: dict[str, Any]
    execution_assumptions: list[str]
    metrics: dict[str, Any]
    equity_curve: list[dict[str, Any]]
    drawdown_curve: list[dict[str, Any]]
    trades: list[dict[str, Any]]
    segments: dict[str, Any] | None = None
    comparisons: list[dict[str, Any]] | None = None
    comparison_note: str | None = None
    disclaimer: str | None = None
