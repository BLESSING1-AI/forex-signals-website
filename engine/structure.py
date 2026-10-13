"""
Price Action Structure Detection
Implements swing detection, trend bias, and basic zone identification
"""

import pandas as pd
import numpy as np
from typing import List, Tuple, Optional


def find_swing_points(df: pd.DataFrame, left: int = 3, right: int = 3) -> pd.DataFrame:
    """
    Detect swing highs and swing lows.
    A swing high is a high higher than `left` bars before and `right` bars after.
    """
    highs = df["high"].values
    lows = df["low"].values

    swing_high = np.full(len(df), False)
    swing_low = np.full(len(df), False)

    for i in range(left, len(df) - right):
        if highs[i] == max(highs[i - left: i + right + 1]):
            swing_high[i] = True
        if lows[i] == min(lows[i - left: i + right + 1]):
            swing_low[i] = True

    result = df.copy()
    result["swing_high"] = swing_high
    result["swing_low"] = swing_low
    return result


def get_recent_swings(df: pd.DataFrame, n: int = 6) -> dict:
    """
    Return the most recent swing highs and lows
    """
    swings = find_swing_points(df)

    recent_highs = swings[swings["swing_high"]].tail(n)
    recent_lows = swings[swings["swing_low"]].tail(n)

    return {
        "highs": list(zip(recent_highs.index, recent_highs["high"])),
        "lows": list(zip(recent_lows.index, recent_lows["low"]))
    }


def determine_bias(df: pd.DataFrame) -> str:
    """
    Simple structure-based bias.
    Looks at the last few swing points to decide HH/HL (bullish) or LH/LL (bearish).
    Returns: "bullish", "bearish", or "neutral"
    """
    swings = get_recent_swings(df, n=4)

    highs = [h[1] for h in swings["highs"]]
    lows = [l[1] for l in swings["lows"]]

    if len(highs) < 2 or len(lows) < 2:
        return "neutral"

    # Higher Highs + Higher Lows
    hh = highs[-1] > highs[-2]
    hl = lows[-1] > lows[-2]

    # Lower Highs + Lower Lows
    lh = highs[-1] < highs[-2]
    ll = lows[-1] < lows[-2]

    if hh and hl:
        return "bullish"
    if lh and ll:
        return "bearish"

    return "neutral"


def detect_engulfing(df: pd.DataFrame) -> Optional[str]:
    """
    Detect bullish or bearish engulfing on the last closed candle.
    Returns "bullish", "bearish", or None
    """
    if len(df) < 2:
        return None

    prev = df.iloc[-2]
    curr = df.iloc[-1]

    prev_body = abs(prev["close"] - prev["open"])
    curr_body = abs(curr["close"] - curr["open"])

    # Bullish engulfing
    if (prev["close"] < prev["open"] and
        curr["close"] > curr["open"] and
        curr["open"] <= prev["close"] and
        curr["close"] >= prev["open"] and
        curr_body > prev_body * 0.8):
        return "bullish"

    # Bearish engulfing
    if (prev["close"] > prev["open"] and
        curr["close"] < curr["open"] and
        curr["open"] >= prev["close"] and
        curr["close"] <= prev["open"] and
        curr_body > prev_body * 0.8):
        return "bearish"

    return None


def detect_pin_bar(df: pd.DataFrame, wick_ratio: float = 2.0) -> Optional[str]:
    """
    Detect pin bar (long wick rejection).
    Returns "bullish", "bearish", or None
    """
    if len(df) < 1:
        return None

    c = df.iloc[-1]
    body = abs(c["close"] - c["open"])
    upper_wick = c["high"] - max(c["open"], c["close"])
    lower_wick = min(c["open"], c["close"]) - c["low"]
    total_range = c["high"] - c["low"]

    if total_range == 0:
        return None

    # Bullish pin (long lower wick)
    if lower_wick >= body * wick_ratio and upper_wick <= body * 0.5 and c["close"] > c["open"]:
        return "bullish"

    # Bearish pin (long upper wick)
    if upper_wick >= body * wick_ratio and lower_wick <= body * 0.5 and c["close"] < c["open"]:
        return "bearish"

    return None


def find_nearby_structure_level(df: pd.DataFrame, direction: str, lookback: int = 30) -> Optional[float]:
    """
    Find a recent swing high/low to use as structure-based stop reference
    """
    swings = find_swing_points(df.tail(lookback + 10))

    if direction == "bullish":
        lows = swings[swings["swing_low"]]
        if not lows.empty:
            return float(lows["low"].iloc[-1])
    else:
        highs = swings[swings["swing_high"]]
        if not highs.empty:
            return float(highs["high"].iloc[-1])

    return None
