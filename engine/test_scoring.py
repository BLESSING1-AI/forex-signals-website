"""Lightweight scoring tests (no network)."""
import pandas as pd
from scoring import score_setup
from state_store import fingerprint

def _synth(n=120, trend=2.0, start=4000.0):
    rows = []
    price = start
    for i in range(n):
        o = price
        c = price + trend * (1.5 + (i % 3))
        h = max(o, c) + 2
        l = min(o, c) - 1.5
        rows.append({"open": o, "high": h, "low": l, "close": c, "volume": 100})
        price = c
    idx = pd.date_range("2026-01-01", periods=n, freq="15min", tz="UTC")
    return pd.DataFrame(rows, index=idx)

def test_strong_bullish_scores_high():
    m15 = _synth(120, trend=2.0)
    h4 = m15.resample("4h").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna()
    d1 = m15.resample("1D").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna()
    s = score_setup(d1, h4, m15, m15)
    assert s is not None, "expected a setup"
    assert s["score"] >= 68, s
    assert s["direction"] == "BUY"
    assert s["rr"] >= 1.8
    print("test_strong_bullish_scores_high OK", s["score"], s["tier"], s["rr"])

def test_flat_market_low_or_none():
    m15 = _synth(80, trend=0.02)
    h4 = m15.resample("4h").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna()
    d1 = h4.copy()
    s = score_setup(d1, h4, m15, m15)
    if s is not None:
        assert s["score"] < 85
    print("test_flat_market_low_or_none OK", None if not s else s["score"])

def test_fingerprint_stable():
    a = {
        "pair": "XAUUSD",
        "direction": "BUY",
        "entry_zone": "4100.2-4102.8",
        "model": "breakout_momentum",
        "structure_level": 4095.0,
    }
    b = {
        "pair": "XAUUSD",
        "direction": "BUY",
        "entry_zone": "4101.0-4103.1",
        "model": "breakout_momentum",
        "structure_level": 4095.0,
    }
    assert fingerprint(a) == fingerprint(b)
    print("test_fingerprint_stable OK")

if __name__ == "__main__":
    test_strong_bullish_scores_high()
    test_flat_market_low_or_none()
    test_fingerprint_stable()
    print("ALL TESTS PASSED")
