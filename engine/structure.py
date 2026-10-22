"""
Price Action structure helpers + BOS / CHoCH / FVG / liquidity sweep
"""
import pandas as pd
import numpy as np
from typing import Optional, Tuple, Dict, Any

def find_swing_points(df: pd.DataFrame, left: int = 3, right: int = 3) -> pd.DataFrame:
    highs = df["high"].values
    lows = df["low"].values
    swing_high = np.full(len(df), False)
    swing_low = np.full(len(df), False)
    for i in range(left, len(df) - right):
        if highs[i] == max(highs[i - left : i + right + 1]):
            swing_high[i] = True
        if lows[i] == min(lows[i - left : i + right + 1]):
            swing_low[i] = True
    out = df.copy()
    out["swing_high"] = swing_high
    out["swing_low"] = swing_low
    return out

def get_recent_swings(df: pd.DataFrame, n: int = 6) -> dict:
    s = find_swing_points(df)
    highs = s[s["swing_high"]].tail(n)
    lows = s[s["swing_low"]].tail(n)
    return {
        "highs": list(zip(highs.index, highs["high"].astype(float))),
        "lows": list(zip(lows.index, lows["low"].astype(float))),
    }

def determine_bias(df: pd.DataFrame) -> str:
    swings = get_recent_swings(df, n=4)
    highs = [h[1] for h in swings["highs"]]
    lows = [l[1] for l in swings["lows"]]
    if len(highs) < 2 or len(lows) < 2:
        return "neutral"
    hh = highs[-1] > highs[-2]
    hl = lows[-1] > lows[-2]
    lh = highs[-1] < highs[-2]
    ll = lows[-1] < lows[-2]
    if hh and hl:
        return "bullish"
    if lh and ll:
        return "bearish"
    return "neutral"

def detect_engulfing(df: pd.DataFrame) -> Optional[str]:
    if len(df) < 2:
        return None
    prev, curr = df.iloc[-2], df.iloc[-1]
    prev_body = abs(prev["close"] - prev["open"])
    curr_body = abs(curr["close"] - curr["open"])
    if (
        prev["close"] < prev["open"]
        and curr["close"] > curr["open"]
        and curr["open"] <= prev["close"]
        and curr["close"] >= prev["open"]
        and curr_body > prev_body * 0.8
    ):
        return "bullish"
    if (
        prev["close"] > prev["open"]
        and curr["close"] < curr["open"]
        and curr["open"] >= prev["close"]
        and curr["close"] <= prev["open"]
        and curr_body > prev_body * 0.8
    ):
        return "bearish"
    return None

def detect_pin_bar(df: pd.DataFrame, wick_ratio: float = 2.0) -> Optional[str]:
    if len(df) < 1:
        return None
    c = df.iloc[-1]
    body = abs(c["close"] - c["open"])
    upper = c["high"] - max(c["open"], c["close"])
    lower = min(c["open"], c["close"]) - c["low"]
    total = c["high"] - c["low"]
    if total == 0:
        return None
    if lower >= body * wick_ratio and upper <= body * 0.5 and c["close"] > c["open"]:
        return "bullish"
    if upper >= body * wick_ratio and lower <= body * 0.5 and c["close"] < c["open"]:
        return "bearish"
    return None

def find_nearby_structure_level(df: pd.DataFrame, direction: str, lookback: int = 30):
    s = find_swing_points(df.tail(lookback + 10))
    if direction == "bullish":
        lows = s[s["swing_low"]]
        if not lows.empty:
            return float(lows["low"].iloc[-1])
    else:
        highs = s[s["swing_high"]]
        if not highs.empty:
            return float(highs["high"].iloc[-1])
    return None

def detect_bos(df: pd.DataFrame) -> Optional[str]:
    """Break of structure vs last confirmed swing."""
    if len(df) < 15:
        return None
    swings = get_recent_swings(df, n=4)
    highs = [h[1] for h in swings["highs"]]
    lows = [l[1] for l in swings["lows"]]
    price = float(df["close"].iloc[-1])
    if len(highs) >= 2 and price > highs[-2] and highs[-1] >= highs[-2]:
        return "bullish"
    if len(lows) >= 2 and price < lows[-2] and lows[-1] <= lows[-2]:
        return "bearish"
    # Simple close beyond prior swing
    if len(highs) >= 1 and price > highs[-1] * 1.0002:
        return "bullish"
    if len(lows) >= 1 and price < lows[-1] * 0.9998:
        return "bearish"
    return None

def detect_choch(df: pd.DataFrame) -> Optional[str]:
    """Change of character: bias flip with a break against prior structure."""
    if len(df) < 20:
        return None
    earlier = df.iloc[:-5]
    recent = df.tail(12)
    old_bias = determine_bias(earlier) if len(earlier) >= 15 else "neutral"
    bos = detect_bos(recent)
    if old_bias == "bearish" and bos == "bullish":
        return "bullish"
    if old_bias == "bullish" and bos == "bearish":
        return "bearish"
    return None

def detect_liquidity_sweep(df: pd.DataFrame) -> Optional[str]:
    """Wick beyond recent swing then close back inside (sweep)."""
    if len(df) < 12:
        return None
    swings = get_recent_swings(df.iloc[:-1], n=4)
    highs = [h[1] for h in swings["highs"]]
    lows = [l[1] for l in swings["lows"]]
    c = df.iloc[-1]
    body_mid = (float(c["open"]) + float(c["close"])) / 2
    if highs:
        sh = highs[-1]
        if float(c["high"]) > sh and float(c["close"]) < sh and body_mid < sh:
            return "bearish"  # swept highs → often sell
    if lows:
        sl = lows[-1]
        if float(c["low"]) < sl and float(c["close"]) > sl and body_mid > sl:
            return "bullish"  # swept lows → often buy
    return None

def detect_fvg(df: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """3-candle fair value gap. Returns zone + direction."""
    if len(df) < 3:
        return None
    a, b, c = df.iloc[-3], df.iloc[-2], df.iloc[-1]
    # Bullish FVG: low of c > high of a
    if float(c["low"]) > float(a["high"]):
        return {
            "direction": "bullish",
            "low": float(a["high"]),
            "high": float(c["low"]),
        }
    # Bearish FVG: high of c < low of a
    if float(c["high"]) < float(a["low"]):
        return {
            "direction": "bearish",
            "low": float(c["high"]),
            "high": float(a["low"]),
        }
    return None

def displacement_metrics(df: pd.DataFrame, bars: int = 5) -> Tuple[float, float]:
    chunk = df.tail(bars)
    net = float(chunk["close"].iloc[-1] - chunk["open"].iloc[0])
    rng = float(chunk["high"].max() - chunk["low"].min())
    return net, rng
