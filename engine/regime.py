"""Market regime detection — independent of entry scoring."""
from __future__ import annotations
from typing import Optional, Dict, Any
import pandas as pd
from indicators import atr, snapshot, trend_from_emas


def detect_regime(
    m15: Optional[pd.DataFrame],
    h1: Optional[pd.DataFrame] = None,
    h4: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
    df = m15 if m15 is not None and not m15.empty else h1
    if df is None or df.empty or len(df) < 40:
        return {"regime": "unknown", "volatility": "unknown", "trend": "unknown"}

    snap = snapshot(df)
    trend = trend_from_emas(snap)
    a = snap.get("atr14") or 0.0
    recent_range = float(df["high"].tail(10).max() - df["low"].tail(10).min())
    longer_range = float(df["high"].tail(40).max() - df["low"].tail(40).min()) or 1

    atr_series = atr(df, 14).dropna()
    vol_label = "normal"
    if len(atr_series) >= 30:
        med = float(atr_series.tail(50).median() or a)
        if a > med * 1.6:
            vol_label = "high"
        elif a < med * 0.65:
            vol_label = "low"

    compression = recent_range / longer_range
    regime = "ranging"
    if vol_label == "high" and trend in ("bullish", "bearish"):
        regime = "trending_up" if trend == "bullish" else "trending_down"
    elif vol_label == "high":
        regime = "high_volatility"
    elif compression < 0.35:
        regime = "consolidation"
    elif vol_label == "low":
        regime = "low_volatility"
    elif trend == "bullish":
        regime = "trending_up"
    elif trend == "bearish":
        regime = "trending_down"

    rsi = snap.get("rsi14")
    if rsi is not None:
        if regime == "trending_up" and rsi >= 72:
            regime = "potential_reversal"
        elif regime == "trending_down" and rsi <= 28:
            regime = "potential_reversal"

    htf_trend = "unknown"
    if h4 is not None and not h4.empty:
        htf_trend = trend_from_emas(snapshot(h4))
    elif h1 is not None and not h1.empty:
        htf_trend = trend_from_emas(snapshot(h1))

    return {
        "regime": regime,
        "volatility": vol_label,
        "trend": trend,
        "htf_trend": htf_trend,
        "atr": round(a, 4) if a else None,
        "rsi": round(rsi, 2) if rsi is not None else None,
        "compression": round(compression, 3),
        "indicators": {k: v for k, v in snap.items() if k != "price"},
    }
