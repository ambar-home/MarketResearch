"""Request / response models. Access tokens never appear in responses."""

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
    short_sma: int = Field(6, ge=2, le=100, description="Short SMA period")
    long_sma: int = Field(30, ge=3, le=300, description="Long SMA period")
    lookback_days: int = Field(400, ge=40, le=2000, description="Daily history lookback")
    max_stocks: int = Field(100, ge=1, le=100, description="Max Nifty 100 stocks to scan")


class SmaSignalRow(BaseModel):
    rank: int
    ticker: str
    company: str
    crossover_type: str
    crossover_date: str
    close: float
    sma_short: float
    sma_long: float


class SmaCrossoverResponse(BaseModel):
    short_sma: int
    long_sma: int
    lookback_days: int
    max_stocks: int
    scanned: int
    signals_found: int
    errors: int
    signals: list[SmaSignalRow]
