"""
Signal quality scoring and risk/reward research helpers.

Scores are INITIAL HEURISTICS (configurable weights), not probabilities.
"""

from __future__ import annotations

from typing import Any

from app.config import ScoreBands, ScoreWeights, settings


def _clamp(value: float, low: float = 0.0, high: float | None = None) -> float:
    high = high if high is not None else value
    return max(low, min(value, high))


def build_risk_reward(
    side: str,
    close: float,
    atr_value: float | None,
    atr_multiplier: float | None = None,
    target_r_multiple: float | None = None,
    swing_low: float | None = None,
    swing_high: float | None = None,
) -> dict[str, Any]:
    """
    Informational risk/reward framework only.
    Does not predict that stop/target will be hit.
    """
    atr_multiplier = (
        atr_multiplier if atr_multiplier is not None else settings.risk.atr_stop_multiplier
    )
    target_r_multiple = (
        target_r_multiple if target_r_multiple is not None else settings.risk.target_r_multiple
    )

    if atr_value is None or atr_value <= 0 or close <= 0:
        return {
            "entry_reference": round(close, 2),
            "stop_reference": None,
            "target_reference": None,
            "risk": None,
            "reward": None,
            "ratio": None,
            "stop_method": f"ATR_{atr_multiplier}X",
            "available": False,
        }

    if side.upper() == "BULLISH":
        atr_stop = close - (atr_value * atr_multiplier)
        stop = atr_stop
        if swing_low is not None:
            stop = min(atr_stop, swing_low)
        risk = close - stop
        target = close + (risk * target_r_multiple) if risk > 0 else None
    else:
        atr_stop = close + (atr_value * atr_multiplier)
        stop = atr_stop
        if swing_high is not None:
            stop = max(atr_stop, swing_high)
        risk = stop - close
        target = close - (risk * target_r_multiple) if risk > 0 else None

    ratio = None
    reward = None
    if risk and risk > 0 and target is not None:
        reward = abs(target - close)
        ratio = round(reward / risk, 2)

    return {
        "entry_reference": round(close, 2),
        "stop_reference": round(stop, 2),
        "target_reference": round(target, 2) if target is not None else None,
        "risk": round(risk, 2) if risk is not None else None,
        "reward": round(reward, 2) if reward is not None else None,
        "ratio": ratio,
        "stop_method": f"ATR_{atr_multiplier}X",
        "available": ratio is not None,
    }


def classify_score(score: int, side: str, bands: ScoreBands | None = None) -> str:
    bands = bands or settings.score_bands
    side = side.upper()
    prefix = "BULLISH" if side == "BULLISH" else "BEARISH"

    if score >= bands.strong:
        strength = "STRONG"
    elif score >= bands.good:
        strength = "GOOD"
    elif score >= bands.moderate:
        strength = "MODERATE"
    elif score >= bands.weak:
        strength = "WEAK"
    else:
        return f"AVOID_{prefix}" if side in {"BULLISH", "BEARISH"} else "AVOID_LOW_CONFIDENCE"

    return f"{strength}_{prefix}"


def score_signal(
    *,
    side: str,
    long_sma_direction: str,
    price_above_long_sma: bool | None,
    volume_confirmation: str,
    rsi_status: str,
    market_trend: str,
    sector_trend: str,
    extension_status: str,
    risk_reward_ratio: float | None,
    weights: ScoreWeights | None = None,
) -> dict[str, Any]:
    """
    Compute 0-100 research score with explainable breakdown.
    Bullish and bearish use mirrored criteria.
    """
    weights = weights or settings.score_weights
    side = side.upper()
    is_bullish = side == "BULLISH"
    breakdown: list[dict[str, Any]] = []

    def add(factor: str, score: float, max_score: int, status: str, reason: str) -> None:
        breakdown.append(
            {
                "factor": factor,
                "score": round(score, 2),
                "max_score": max_score,
                "status": status,
                "reason": reason,
            }
        )

    # 1) Crossover present
    add(
        "SMA Crossover",
        weights.crossover,
        weights.crossover,
        "PASS",
        f"{'Bullish' if is_bullish else 'Bearish'} SMA crossover detected",
    )

    # 2) Price vs long SMA
    if price_above_long_sma is None:
        add("Price vs Long SMA", 0, weights.price_vs_long_sma, "UNKNOWN", "Price/SMA data unavailable")
    elif is_bullish and price_above_long_sma:
        add(
            "Price vs Long SMA",
            weights.price_vs_long_sma,
            weights.price_vs_long_sma,
            "PASS",
            "Close is above long SMA",
        )
    elif (not is_bullish) and (not price_above_long_sma):
        add(
            "Price vs Long SMA",
            weights.price_vs_long_sma,
            weights.price_vs_long_sma,
            "PASS",
            "Close is below long SMA",
        )
    else:
        add(
            "Price vs Long SMA",
            weights.price_vs_long_sma * 0.25,
            weights.price_vs_long_sma,
            "PARTIAL",
            "Price is on the opposite side of long SMA",
        )

    # 3) Long SMA slope
    if is_bullish:
        if long_sma_direction == "RISING":
            add("Long SMA Trend", weights.long_sma_slope, weights.long_sma_slope, "PASS", "Long SMA is rising")
        elif long_sma_direction == "FLAT":
            add(
                "Long SMA Trend",
                weights.long_sma_slope * 0.5,
                weights.long_sma_slope,
                "PARTIAL",
                "Long SMA is flat",
            )
        elif long_sma_direction == "FALLING":
            add(
                "Long SMA Trend",
                weights.long_sma_slope * 0.15,
                weights.long_sma_slope,
                "FAIL",
                "Long SMA is falling against bullish crossover",
            )
        else:
            add("Long SMA Trend", 0, weights.long_sma_slope, "UNKNOWN", "Slope unavailable")
    else:
        if long_sma_direction == "FALLING":
            add("Long SMA Trend", weights.long_sma_slope, weights.long_sma_slope, "PASS", "Long SMA is falling")
        elif long_sma_direction == "FLAT":
            add(
                "Long SMA Trend",
                weights.long_sma_slope * 0.5,
                weights.long_sma_slope,
                "PARTIAL",
                "Long SMA is flat",
            )
        elif long_sma_direction == "RISING":
            add(
                "Long SMA Trend",
                weights.long_sma_slope * 0.15,
                weights.long_sma_slope,
                "FAIL",
                "Long SMA is rising against bearish crossover",
            )
        else:
            add("Long SMA Trend", 0, weights.long_sma_slope, "UNKNOWN", "Slope unavailable")

    # 4) Volume
    if volume_confirmation == "STRONG":
        add("Volume", weights.volume, weights.volume, "PASS", "Volume strongly above average")
    elif volume_confirmation == "NORMAL":
        add(
            "Volume",
            weights.volume * 0.65,
            weights.volume,
            "PARTIAL",
            "Volume near or modestly above average",
        )
    elif volume_confirmation == "WEAK":
        add("Volume", weights.volume * 0.2, weights.volume, "FAIL", "Volume below average")
    else:
        add("Volume", 0, weights.volume, "UNKNOWN", "Volume data unavailable")

    # 5) Momentum / RSI
    if rsi_status == "SUPPORTIVE":
        add("Momentum (RSI)", weights.momentum, weights.momentum, "PASS", "RSI supports signal direction")
    elif rsi_status == "NEUTRAL":
        add(
            "Momentum (RSI)",
            weights.momentum * 0.55,
            weights.momentum,
            "PARTIAL",
            "RSI is neutral",
        )
    elif rsi_status == "EXTENDED":
        add(
            "Momentum (RSI)",
            weights.momentum * 0.25,
            weights.momentum,
            "FAIL",
            "RSI looks extended for this side",
        )
    elif rsi_status == "WEAK":
        add(
            "Momentum (RSI)",
            weights.momentum * 0.2,
            weights.momentum,
            "FAIL",
            "RSI does not support signal direction",
        )
    else:
        add("Momentum (RSI)", 0, weights.momentum, "UNKNOWN", "RSI unavailable")

    # 6) Market
    desired = "BULLISH" if is_bullish else "BEARISH"
    if market_trend == desired:
        add("Market Context", weights.market, weights.market, "PASS", f"Nifty trend is {market_trend}")
    elif market_trend == "NEUTRAL":
        add(
            "Market Context",
            weights.market * 0.45,
            weights.market,
            "PARTIAL",
            "Nifty trend is neutral",
        )
    elif market_trend in {"BULLISH", "BEARISH"}:
        add(
            "Market Context",
            weights.market * 0.15,
            weights.market,
            "FAIL",
            f"Nifty trend ({market_trend}) conflicts with signal",
        )
    else:
        add("Market Context", 0, weights.market, "UNKNOWN", "Market context unavailable")

    # 7) Sector
    if sector_trend == desired:
        add("Sector Context", weights.sector, weights.sector, "PASS", f"Sector trend is {sector_trend}")
    elif sector_trend == "NEUTRAL":
        add(
            "Sector Context",
            weights.sector * 0.45,
            weights.sector,
            "PARTIAL",
            "Sector trend is neutral",
        )
    elif sector_trend in {"BULLISH", "BEARISH"}:
        add(
            "Sector Context",
            weights.sector * 0.15,
            weights.sector,
            "FAIL",
            f"Sector trend ({sector_trend}) conflicts with signal",
        )
    else:
        # Unavailable — do not punish full weight; partial credit for honesty
        add(
            "Sector Context",
            weights.sector * 0.35,
            weights.sector,
            "UNKNOWN",
            "Sector confirmation unavailable",
        )

    # 8) Extension
    if extension_status == "NORMAL":
        add("Overextension", weights.extension, weights.extension, "PASS", "Price not overextended vs short SMA")
    elif extension_status == "ELEVATED":
        add(
            "Overextension",
            weights.extension * 0.5,
            weights.extension,
            "PARTIAL",
            "Price move vs short SMA is elevated",
        )
    elif extension_status == "EXTENDED":
        add(
            "Overextension",
            weights.extension * 0.15,
            weights.extension,
            "FAIL",
            "Price looks extended vs short SMA",
        )
    else:
        add("Overextension", 0, weights.extension, "UNKNOWN", "Extension status unavailable")

    # 9) Risk/reward structure
    if risk_reward_ratio is None:
        add("Risk/Reward", 0, weights.risk_reward, "UNKNOWN", "Risk/reward unavailable")
    elif risk_reward_ratio >= 2.0:
        add(
            "Risk/Reward",
            weights.risk_reward,
            weights.risk_reward,
            "PASS",
            f"Hypothetical R:R is {risk_reward_ratio:.2f}",
        )
    elif risk_reward_ratio >= 1.5:
        add(
            "Risk/Reward",
            weights.risk_reward * 0.7,
            weights.risk_reward,
            "PARTIAL",
            f"Hypothetical R:R is {risk_reward_ratio:.2f}",
        )
    else:
        add(
            "Risk/Reward",
            weights.risk_reward * 0.25,
            weights.risk_reward,
            "FAIL",
            f"Hypothetical R:R is low ({risk_reward_ratio:.2f})",
        )

    total = int(round(sum(item["score"] for item in breakdown)))
    total = int(_clamp(total, 0, 100))
    classification = classify_score(total, side)

    passed = [b["reason"] for b in breakdown if b["status"] == "PASS"]
    summary_bits = passed[:4] if passed else ["Limited confirmation across factors"]
    summary = (
        f"{'Bullish' if is_bullish else 'Bearish'} research candidate. "
        + "; ".join(summary_bits)
        + ". This is a research signal, not an automatic trade instruction."
    )

    return {
        "score": total,
        "classification": classification,
        "summary": summary,
        "score_breakdown": breakdown,
    }
