"""
Indian equity transaction-cost model (configurable).

Rates should be verified against current Zerodha / NSE schedules.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from app.config import TransactionCostRates, settings


def apply_slippage(price: float, side: str, slippage_bps: float) -> float:
    """
    side: BUY worsens upward, SELL worsens downward.
    slippage_bps: basis points of adverse price move.
    """
    if price <= 0:
        return price
    slip = price * (slippage_bps / 10_000.0)
    if side.upper() == "BUY":
        return price + slip
    return price - slip


def estimate_round_trip_costs(
    buy_price: float,
    sell_price: float,
    quantity: int,
    rates: TransactionCostRates | None = None,
    include_slippage_in_prices: bool = False,
) -> dict[str, Any]:
    """
    Approximate delivery-style equity costs for one round trip.
    Returns absolute INR cost breakdown.
    """
    rates = rates or settings.costs
    if quantity <= 0 or buy_price <= 0 or sell_price <= 0:
        return {
            "buy_turnover": 0.0,
            "sell_turnover": 0.0,
            "total_cost": 0.0,
            "breakdown": {},
            "rates_used": asdict(rates),
        }

    buy_turnover = buy_price * quantity
    sell_turnover = sell_price * quantity

    # Brokerage (often 0 for Zerodha delivery)
    buy_brokerage = min(buy_turnover * rates.brokerage_rate, rates.brokerage_cap or buy_turnover)
    sell_brokerage = min(sell_turnover * rates.brokerage_rate, rates.brokerage_cap or sell_turnover)

    stt_buy = buy_turnover * rates.stt_buy_rate
    stt_sell = sell_turnover * rates.stt_sell_rate

    exch_buy = buy_turnover * rates.exchange_txn_rate
    exch_sell = sell_turnover * rates.exchange_txn_rate

    sebi_buy = buy_turnover * rates.sebi_rate
    sebi_sell = sell_turnover * rates.sebi_rate

    stamp_buy = buy_turnover * rates.stamp_duty_buy_rate

    gst_base = buy_brokerage + sell_brokerage + exch_buy + exch_sell
    gst = gst_base * rates.gst_on_brokerage_and_txn

    total = (
        buy_brokerage
        + sell_brokerage
        + stt_buy
        + stt_sell
        + exch_buy
        + exch_sell
        + sebi_buy
        + sebi_sell
        + stamp_buy
        + gst
    )

    return {
        "buy_turnover": round(buy_turnover, 2),
        "sell_turnover": round(sell_turnover, 2),
        "total_cost": round(total, 2),
        "breakdown": {
            "brokerage": round(buy_brokerage + sell_brokerage, 2),
            "stt": round(stt_buy + stt_sell, 2),
            "exchange_txn": round(exch_buy + exch_sell, 2),
            "sebi": round(sebi_buy + sebi_sell, 2),
            "stamp_duty": round(stamp_buy, 2),
            "gst": round(gst, 2),
        },
        "rates_used": asdict(rates),
        "note": (
            "Configurable approximate costs. Verify against current Zerodha/NSE fee schedules. "
            f"include_slippage_in_prices={include_slippage_in_prices}"
        ),
    }


def costed_fill_price(price: float, side: str, apply_costs: bool, slippage_bps: float) -> float:
    if not apply_costs:
        return price
    return apply_slippage(price, side, slippage_bps)
