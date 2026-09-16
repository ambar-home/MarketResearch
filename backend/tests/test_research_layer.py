"""Tests for research flags, sentiment tags, and careful decisions."""

from app.services.research_layer import (
    careful_decision,
    classify_headlines,
    earnings_context,
    valuation_flag,
)


def test_sentiment_unclear_without_enough_headlines():
    out = classify_headlines(["Only one headline"])
    assert out["tag"] == "UNCLEAR"


def test_sentiment_positive_and_negative():
    pos = classify_headlines(["Stock beats estimates", "Analyst upgrade and strong growth"])
    neg = classify_headlines(["Company misses estimates", "Broker downgrade after weak results"])
    assert pos["tag"] == "POSITIVE"
    assert neg["tag"] == "NEGATIVE"


def test_valuation_flags():
    assert valuation_flag(None)["flag"] == "UNKNOWN"
    assert valuation_flag(12)["flag"] == "LOW_PE"
    assert valuation_flag(25)["flag"] == "MID_PE"
    assert valuation_flag(55)["flag"] == "HIGH_PE"


def test_earnings_near():
    out = earnings_context("2026-09-18", today=__import__("datetime").date(2026, 9, 16))
    assert out["event_risk"] == "NEAR"


def test_skip_unclear_or_extended():
    skip = careful_decision(
        score=85,
        extension="EXTENDED",
        volume="STRONG",
        side="BULLISH",
        long_sma_direction="RISING",
        sentiment="POSITIVE",
        event_risk="NOT_NEAR",
    )
    assert skip["action"] == "SKIP"

    unclear = careful_decision(
        score=80,
        extension="NORMAL",
        volume="STRONG",
        side="BULLISH",
        long_sma_direction="RISING",
        sentiment="UNCLEAR",
        event_risk="NOT_NEAR",
    )
    assert unclear["action"] == "SKIP"


def test_research_candidate_when_aligned():
    out = careful_decision(
        score=82,
        extension="NORMAL",
        volume="STRONG",
        side="BULLISH",
        long_sma_direction="RISING",
        sentiment="POSITIVE",
        event_risk="NOT_NEAR",
    )
    assert out["action"] == "RESEARCH_CANDIDATE"
