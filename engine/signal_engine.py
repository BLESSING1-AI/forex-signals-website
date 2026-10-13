"""
Main Signal Engine - Strict Mode XAUUSD + Event Signals
"""
from datetime import datetime, timezone
from data_fetcher import get_multi_timeframe_data
from structure import (
    determine_bias, detect_engulfing, detect_pin_bar,
    find_nearby_structure_level
)
from telegram_poster import send_signal
from config import (
    MAX_SIGNALS_PER_DAY, XAU_SL_BUFFER, MIN_RR_TP1,
    DEFAULT_RISK_PERCENT, NEWS_BLACKOUT,
    LONDON_START, LONDON_END, NY_START, NY_END
)

# Event engine
try:
    from event_engine import run_event_cycle
except Exception:
    run_event_cycle = None

signals_today = 0
last_signal_date = None

def is_session_active() -> bool:
    hour = datetime.now(timezone.utc).hour
    return (LONDON_START <= hour < LONDON_END) or (NY_START <= hour < NY_END)

def calculate_targets(entry: float, stop: float, direction: str) -> dict:
    risk = abs(entry - stop)
    if direction == "bullish":
        return {
            "tp1": round(entry + risk * 1.5, 2),
            "tp2": round(entry + risk * 3.0, 2),
            "tp3": round(entry + risk * 5.0, 2),
        }
    return {
        "tp1": round(entry - risk * 1.5, 2),
        "tp2": round(entry - risk * 3.0, 2),
        "tp3": round(entry - risk * 5.0, 2),
    }

def generate_signal():
    global signals_today, last_signal_date
    today = datetime.now(timezone.utc).date()
    if last_signal_date != today:
        signals_today = 0
        last_signal_date = today

    if signals_today >= MAX_SIGNALS_PER_DAY:
        print("Max technical signals reached for today")
        return None
    if NEWS_BLACKOUT:
        print("News blackout flag active")
        return None
    if not is_session_active():
        print("Outside London/NY session")
        return None

    print("Fetching multi-timeframe data...")
    data = get_multi_timeframe_data()
    d1, h4, m15, m5 = data.get("1d"), data.get("4h"), data.get("15m"), data.get("5m")

    if any(x is None or x.empty for x in [d1, h4, m15]):
        print("Insufficient data")
        return None

    d1_bias = determine_bias(d1)
    h4_bias = determine_bias(h4)
    print(f"D1: {d1_bias} | H4: {h4_bias}")

    if d1_bias == "neutral" or h4_bias == "neutral" or d1_bias != h4_bias:
        print("No clear aligned HTF bias")
        return None

    bias = d1_bias
    confirmation = None
    for name, df in [("15m", m15), ("5m", m5)]:
        if df is None or df.empty:
            continue
        engulf = detect_engulfing(df)
        pin = detect_pin_bar(df)
        if bias == "bullish" and (engulf == "bullish" or pin == "bullish"):
            confirmation = f"{name.upper()} {engulf or pin} confirmation"
            break
        if bias == "bearish" and (engulf == "bearish" or pin == "bearish"):
            confirmation = f"{name.upper()} {engulf or pin} confirmation"
            break

    if not confirmation:
        print("No confirmation candle")
        return None

    structure_level = find_nearby_structure_level(m15, bias)
    if structure_level is None:
        print("No structure level")
        return None

    price = float(m15["close"].iloc[-1])
    if bias == "bullish":
        entry_low = round(price - 1.5, 2)
        entry_high = round(price + 0.5, 2)
        stop = round(structure_level - XAU_SL_BUFFER, 2)
        direction = "BUY"
    else:
        entry_low = round(price - 0.5, 2)
        entry_high = round(price + 1.5, 2)
        stop = round(structure_level + XAU_SL_BUFFER, 2)
        direction = "SELL"

    entry_mid = (entry_low + entry_high) / 2
    risk = abs(entry_mid - stop)
    if risk < 5:
        print("Risk too small")
        return None

    targets = calculate_targets(entry_mid, stop, bias)
    if abs(targets["tp1"] - entry_mid) / risk < MIN_RR_TP1:
        print("RR too low")
        return None

    context = (
        f"• D1 / H4 {bias.capitalize()} Alignment\n"
        f"• {confirmation}\n"
        f"• Structure-based Stop + gold volatility buffer"
    )

    return {
        "pair": "XAUUSD",
        "direction": direction,
        "entry_zone": f"{entry_low} - {entry_high}",
        "stop_loss": str(stop),
        "tp1": str(targets["tp1"]),
        "tp2": str(targets["tp2"]),
        "tp3": str(targets["tp3"]),
        "context": context,
        "risk": f"{DEFAULT_RISK_PERCENT}%",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

def run_once():
    print(f"\n=== Engine Run @ {datetime.now(timezone.utc).isoformat()} ===")

    # 1) Event signals first (NFP, CPI, FOMC, etc.)
    if run_event_cycle:
        try:
            event_posts = run_event_cycle()
            print(f"Event cycle posted: {len(event_posts)} signal(s)")
        except Exception as e:
            print(f"Event engine error: {e}")

    # 2) Pure price-action technical setups
    signal = generate_signal()
    if signal is None:
        print("No high-quality technical setup this cycle")
        return

    print("Technical setup found:", signal)
    if send_signal(signal):
        global signals_today
        signals_today += 1
        print(f"Posted technical signal. Today: {signals_today}/{MAX_SIGNALS_PER_DAY}")

if __name__ == "__main__":
    run_once()
