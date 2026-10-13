"""
Main Signal Engine - Strict Mode XAUUSD
Implements the institutional multi-timeframe price action framework
"""

from datetime import datetime, timezone
import pandas as pd

from data_fetcher import get_multi_timeframe_data
from structure import (
    determine_bias,
    detect_engulfing,
    detect_pin_bar,
    find_nearby_structure_level,
    get_recent_swings
)
from telegram_poster import send_signal, send_message
from config import (
    MAX_SIGNALS_PER_DAY,
    XAU_SL_BUFFER,
    MIN_RR_TP1,
    DEFAULT_RISK_PERCENT,
    NEWS_BLACKOUT
)


# Simple in-memory counter (in production use a database or file)
signals_today = 0
last_signal_date = None


def is_session_active() -> bool:
    """
    Only generate signals during London or New York sessions (UTC)
    """
    now = datetime.now(timezone.utc)
    hour = now.hour

    # London 07:00-16:00 UTC, New York 12:00-21:00 UTC
    london = 7 <= hour < 16
    ny = 12 <= hour < 21
    return london or ny


def calculate_targets(entry: float, stop: float, direction: str) -> dict:
    """
    Calculate 3 TPs based on risk distance
    TP1 ≈ 1.5R, TP2 ≈ 3R, TP3 ≈ 5R
    """
    risk = abs(entry - stop)

    if direction == "bullish":
        tp1 = round(entry + risk * 1.5, 2)
        tp2 = round(entry + risk * 3.0, 2)
        tp3 = round(entry + risk * 5.0, 2)
    else:
        tp1 = round(entry - risk * 1.5, 2)
        tp2 = round(entry - risk * 3.0, 2)
        tp3 = round(entry - risk * 5.0, 2)

    return {"tp1": tp1, "tp2": tp2, "tp3": tp3}


def generate_signal() -> dict | None:
    """
    Core logic following the institutional framework.
    Returns a signal dict or None if no high-quality setup.
    """
    global signals_today, last_signal_date

    today = datetime.now(timezone.utc).date()
    if last_signal_date != today:
        signals_today = 0
        last_signal_date = today

    if signals_today >= MAX_SIGNALS_PER_DAY:
        print("Max signals for today already reached")
        return None

    if NEWS_BLACKOUT:
        print("News blackout active")
        return None

    if not is_session_active():
        print("Outside London / New York session")
        return None

    print("Fetching multi-timeframe data...")
    data = get_multi_timeframe_data()

    d1 = data.get("1d")
    h4 = data.get("4h")
    m15 = data.get("15m")
    m5 = data.get("5m")

    if any(df is None or df.empty for df in [d1, h4, m15]):
        print("Insufficient data")
        return None

    # 1. Higher Timeframe Bias
    d1_bias = determine_bias(d1)
    h4_bias = determine_bias(h4)

    print(f"D1 bias: {d1_bias} | H4 bias: {h4_bias}")

    if d1_bias == "neutral" or h4_bias == "neutral":
        print("No clear HTF bias")
        return None

    if d1_bias != h4_bias:
        print("D1 and H4 bias conflict – skipping")
        return None

    bias = d1_bias   # "bullish" or "bearish"

    # 2. Lower Timeframe Confirmation
    confirmation = None

    # Prefer M15, fall back to M5
    for tf_name, tf_df in [("15m", m15), ("5m", m5)]:
        if tf_df is None or tf_df.empty:
            continue

        engulf = detect_engulfing(tf_df)
        pin = detect_pin_bar(tf_df)

        if bias == "bullish" and (engulf == "bullish" or pin == "bullish"):
            confirmation = f"{tf_name.upper()} {engulf or pin} confirmation"
            break
        if bias == "bearish" and (engulf == "bearish" or pin == "bearish"):
            confirmation = f"{tf_name.upper()} {engulf or pin} confirmation"
            break

    if not confirmation:
        print("No valid confirmation candle")
        return None

    # 3. Structure-based Stop Loss
    structure_level = find_nearby_structure_level(m15, bias)

    if structure_level is None:
        print("Could not find structure level for SL")
        return None

    current_price = float(m15["close"].iloc[-1])

    # Entry zone around current price (small range)
    if bias == "bullish":
        entry_low = round(current_price - 1.5, 2)
        entry_high = round(current_price + 0.5, 2)
        stop = round(structure_level - XAU_SL_BUFFER, 2)
        direction = "BUY"
    else:
        entry_low = round(current_price - 0.5, 2)
        entry_high = round(current_price + 1.5, 2)
        stop = round(structure_level + XAU_SL_BUFFER, 2)
        direction = "SELL"

    entry_mid = (entry_low + entry_high) / 2
    risk = abs(entry_mid - stop)

    if risk < 5:          # too tight for gold
        print("Risk distance too small")
        return None

    targets = calculate_targets(entry_mid, stop, bias)

    # Minimum RR check
    rr_tp1 = abs(targets["tp1"] - entry_mid) / risk
    if rr_tp1 < MIN_RR_TP1:
        print("TP1 RR too low")
        return None

    context_lines = [
        f"• D1 / H4 {bias.capitalize()} Alignment",
        f"• {confirmation}",
        f"• Structure-based Stop with gold volatility buffer"
    ]

    signal = {
        "pair": "XAUUSD",
        "direction": direction,
        "entry_zone": f"{entry_low} - {entry_high}",
        "stop_loss": str(stop),
        "tp1": str(targets["tp1"]),
        "tp2": str(targets["tp2"]),
        "tp3": str(targets["tp3"]),
        "context": "\n".join(context_lines),
        "risk": f"{DEFAULT_RISK_PERCENT}%",
        "generated_at": datetime.now(timezone.utc).isoformat()
    }

    return signal


def run_once():
    """
    Run one full cycle: analyze → generate → post
    """
    print(f"\n=== Signal Engine Run @ {datetime.now(timezone.utc).isoformat()} ===")

    signal = generate_signal()

    if signal is None:
        print("No high-quality setup found this cycle")
        return

    print("High-quality setup found:")
    print(signal)

    success = send_signal(signal)

    if success:
        global signals_today
        signals_today += 1
        print(f"Signal posted. Signals today: {signals_today}/{MAX_SIGNALS_PER_DAY}")
    else:
        print("Failed to post signal")


if __name__ == "__main__":
    run_once()
