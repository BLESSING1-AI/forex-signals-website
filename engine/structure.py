"""
Price Action structure helpers
"""
import pandas as pd
import numpy as np
from typing import Optional

def find_swing_points(df: pd.DataFrame, left: int = 3, right: int = 3) -> pd.DataFrame:
    highs = df["high"].values
    lows = df["low"].values
    swing_high = np.full(len(df), False)
    swing_low = np.full(len(df), False)
    for i in range(left, len(df) - right):
        if highs[i] == max(highs[i-left:i+right+1]):
            swing_high[i] = True
        if lows[i] == min(lows[i-left:i+right+1]):
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
        "highs": list(zip(highs.index, highs["high"])),
        "lows": list(zip(lows.index, lows["low"])),
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
    if (prev["close"] < prev["open"] and curr["close"] > curr["open"] and
        curr["open"] <= prev["close"] and curr["close"] >= prev["open"] and
        curr_body > prev_body * 0.8):
        return "bullish"
    if (prev["close"] > prev["open"] and curr["close"] < curr["open"] and
        curr["open"] >= prev["close"] and curr["close"] <= prev["open"] and
        curr_body > prev_body * 0.8):
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
