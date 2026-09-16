"""Unit tests for signal scoring."""

from app.services.signal_engine import build_risk_reward, classify_score, score_signal


def test_score_strong_bullish_alignment():
    result = score_signal(
        side="BULLISH",
        long_sma_direction="RISING",
        price_above_long_sma=True,
        volume_confirmation="STRONG",
        rsi_status="SUPPORTIVE",
        market_trend="BULLISH",
        sector_trend="BULLISH",
        extension_status="NORMAL",
        risk_reward_ratio=2.0,
    )
    assert result["score"] >= 80
    assert result["classification"] == "STRONG_BULLISH"
    assert abs(sum(b["score"] for b in result["score_breakdown"]) - result["score"]) < 1.5


def test_score_weak_when_conflicts():
    result = score_signal(
        side="BULLISH",
        long_sma_direction="FALLING",
        price_above_long_sma=False,
        volume_confirmation="WEAK",
        rsi_status="WEAK",
        market_trend="BEARISH",
        sector_trend="BEARISH",
        extension_status="EXTENDED",
        risk_reward_ratio=0.8,
    )
    assert result["score"] < 50


def test_classify_bands():
    assert classify_score(85, "BULLISH").startswith("STRONG")
    assert classify_score(70, "BEARISH").startswith("GOOD")
    assert classify_score(55, "BULLISH").startswith("MODERATE")
    assert classify_score(40, "BULLISH").startswith("WEAK")
    assert "AVOID" in classify_score(20, "BULLISH")


def test_risk_reward_bullish():
    rr = build_risk_reward(side="BULLISH", close=100, atr_value=2, atr_multiplier=1.5, target_r_multiple=2)
    assert rr["available"] is True
    assert rr["stop_reference"] < 100
    assert rr["target_reference"] > 100
    assert rr["ratio"] == 2.0
