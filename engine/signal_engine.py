"""Main runner: events + momentum scalps + strict PA"""
from datetime import datetime, timezone
from data_fetcher import get_multi_timeframe_data
from structure import (
    determine_bias, detect_engulfing, detect_pin_bar,
    find_nearby_structure_level,
)
from telegram_poster import send_signal
from config import (
    MAX_SIGNALS_PER_DAY, XAU_SL_BUFFER, MIN_RR_TP1,
    DEFAULT_RISK_PERCENT, NEWS_BLACKOUT,
    LONDON_START, LONDON_END, NY_START, NY_END,
)

try:
    from event_engine import run_event_cycle
except Exception:
    run_event_cycle = None

try:
    from momentum import run_momentum
except Exception:
    run_momentum = None

signals_today = 0
last_signal_date = None

def is_session_active() -> bool:
    hour = datetime.now(timezone.utc).hour
    return (LONDON_START <= hour < LONDON_END) or (NY_START <= hour < NY_END)

def calculate_targets(entry, stop, direction):
    risk = abs(entry - stop)
    if direction == "bullish":
        return {"tp1": round(entry + risk * 1.5, 2), "tp2": round(entry + risk * 3, 2), "tp3": round(entry + risk * 5, 2)}
    return {"tp1": round(entry - risk * 1.5, 2), "tp2": round(entry - risk * 3, 2), "tp3": round(entry - risk * 5, 2)}

def generate_signal():
    global signals_today, last_signal_date
    today = datetime.now(timezone.utc).date()
    if last_signal_date != today:
        signals_today = 0
        last_signal_date = today
    if signals_today >= MAX_SIGNALS_PER_DAY or NEWS_BLACKOUT or not is_session_active():
        return None

    data = get_multi_timeframe_data()
    d1, h4, m15, m5 = data.get("1d"), data.get("4h"), data.get("15m"), data.get("5m")
    if any(x is None or x.empty for x in [d1, h4, m15]):
        return None

    d1_bias, h4_bias = determine_bias(d1), determine_bias(h4)
    if d1_bias == "neutral" or h4_bias == "neutral" or d1_bias != h4_bias:
        return None

    bias = d1_bias
    confirmation = None
    for name, df in [("15m", m15), ("5m", m5)]:
        if df is None or df.empty:
            continue
        engulf, pin = detect_engulfing(df), detect_pin_bar(df)
        if bias == "bullish" and (engulf == "bullish" or pin == "bullish"):
            confirmation = f"{name} {engulf or pin}"
            break
        if bias == "bearish" and (engulf == "bearish" or pin == "bearish"):
            confirmation = f"{name} {engulf or pin}"
            break
    if not confirmation:
        return None

    structure = find_nearby_structure_level(m15, bias)
    if structure is None:
        return None

    price = float(m15["close"].iloc[-1])
    if bias == "bullish":
        el, eh = round(price - 1.5, 2), round(price + 0.5, 2)
        stop = round(structure - XAU_SL_BUFFER, 2)
        direction = "BUY"
    else:
        el, eh = round(price - 0.5, 2), round(price + 1.5, 2)
        stop = round(structure + XAU_SL_BUFFER, 2)
        direction = "SELL"

    mid = (el + eh) / 2
    risk = abs(mid - stop)
    if risk < 5:
        return None
    targets = calculate_targets(mid, stop, bias)
    if abs(targets["tp1"] - mid) / risk < MIN_RR_TP1:
        return None

    return {
        "pair": "XAUUSD",
        "direction": direction,
        "entry_zone": f"{el}-{eh}",
        "stop_loss": str(stop),
        "tp1": str(targets["tp1"]),
        "tp2": str(targets["tp2"]),
        "tp3": str(targets["tp3"]),
    }

def run_once():
    print(f"\n=== Run @ {datetime.now(timezone.utc).isoformat()} ===")

    if run_event_cycle:
        try:
            ev = run_event_cycle()
            print("Events:", ev)
        except Exception as e:
            print("Event error:", e)

    if run_momentum:
        try:
            run_momentum()
        except Exception as e:
            print("Momentum error:", e)

    signal = generate_signal()
    if signal is None:
        print("No strict PA setup")
        return
    if send_signal(signal):
        global signals_today
        signals_today += 1
        print("PA posted", signals_today)

if __name__ == "__main__":
    run_once()
