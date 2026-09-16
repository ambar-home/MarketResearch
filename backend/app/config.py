"""
Central configuration for MarketResearch.

Non-secret strategy defaults and scoring weights live here.
Secrets should use environment variables / .env (never commit).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# backend/ directory (parent of app/)
BACKEND_DIR = Path(__file__).resolve().parent.parent

# Persisted Kite session for local dev (gitignored — never commit)
SESSION_FILE = BACKEND_DIR / ".kite_session.json"

# CORS origins for the Vite frontend
CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

# Official index constituent CSVs (NSE archives)
NIFTY100_CSV_URL = "https://archives.nseindia.com/content/indices/ind_nifty100list.csv"
NIFTY200_CSV_URL = "https://archives.nseindia.com/content/indices/ind_nifty200list.csv"

# Rate limiting between Kite historical calls
KITE_SLEEP_SECONDS = 0.25

# Index names as listed on Kite NSE INDICES segment
NIFTY50_INDEX_NAME = "NIFTY 50"


@dataclass(frozen=True)
class IndicatorDefaults:
    short_sma: int = 6
    long_sma: int = 30
    rsi_period: int = 14
    atr_period: int = 14
    volume_period: int = 20
    slope_lookback: int = 5
    lookback_days: int = 400
    max_stocks: int = 100  # UI/API allow up to 200


@dataclass(frozen=True)
class SlopeThresholds:
    """Percent change thresholds for classifying long-SMA direction."""

    rising_pct: float = 0.15
    falling_pct: float = -0.15


@dataclass(frozen=True)
class VolumeThresholds:
    strong_ratio: float = 1.5
    weak_ratio: float = 1.0


@dataclass(frozen=True)
class ExtensionThresholds:
    """Distance from short SMA % for overextension classification."""

    elevated_pct: float = 3.0
    extended_pct: float = 6.0


@dataclass(frozen=True)
class RiskDefaults:
    atr_stop_multiplier: float = 1.5
    target_r_multiple: float = 2.0


@dataclass(frozen=True)
class ScoreWeights:
    """
    INITIAL HEURISTIC weights (sum = 100).
    Not statistically proven — tune via backtesting.
    """

    crossover: int = 20
    price_vs_long_sma: int = 10
    long_sma_slope: int = 15
    volume: int = 15
    momentum: int = 10
    market: int = 10
    sector: int = 10
    extension: int = 5
    risk_reward: int = 5

    def total(self) -> int:
        return (
            self.crossover
            + self.price_vs_long_sma
            + self.long_sma_slope
            + self.volume
            + self.momentum
            + self.market
            + self.sector
            + self.extension
            + self.risk_reward
        )


@dataclass(frozen=True)
class ScoreBands:
    strong: int = 80
    good: int = 65
    moderate: int = 50
    weak: int = 35


@dataclass(frozen=True)
class TransactionCostRates:
    """
    Approximate Indian equity cash (delivery-style) cost model.
    VERIFY against current Zerodha / NSE fee schedules before relying on results.
    Values are fractions of turnover unless noted.
    """

    brokerage_rate: float = 0.0  # Zerodha equity delivery often ₹0
    brokerage_cap: float = 0.0
    stt_buy_rate: float = 0.001  # 0.10% on buy (delivery)
    stt_sell_rate: float = 0.001  # 0.10% on sell (delivery)
    exchange_txn_rate: float = 0.0000297  # NSE approx
    sebi_rate: float = 0.000001  # ₹10 / crore
    stamp_duty_buy_rate: float = 0.00015  # 0.015% buy
    gst_on_brokerage_and_txn: float = 0.18
    slippage_bps: float = 5.0  # 5 bps default simulated slippage


@dataclass
class AppSettings:
    indicators: IndicatorDefaults = field(default_factory=IndicatorDefaults)
    slope: SlopeThresholds = field(default_factory=SlopeThresholds)
    volume: VolumeThresholds = field(default_factory=VolumeThresholds)
    extension: ExtensionThresholds = field(default_factory=ExtensionThresholds)
    risk: RiskDefaults = field(default_factory=RiskDefaults)
    score_weights: ScoreWeights = field(default_factory=ScoreWeights)
    score_bands: ScoreBands = field(default_factory=ScoreBands)
    costs: TransactionCostRates = field(default_factory=TransactionCostRates)


settings = AppSettings()
