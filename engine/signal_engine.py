"""
Quality daily PA + events + serious momentum
TP order: TP1 furthest (5R) · TP2 (3R) · TP3 closest (1.5R)
"""
from datetime import datetime, timezone
from data_fetcher import get_multi_timeframe_data
from structure import (
    determine_bias, detect_engulfing, detect_pin_bar,
    find_nearby_structure_level,
)
from telegram_poster import send_signal, send_message
from config import (
    MAX_SIGNALS_PER_DAY, XAU_SL_BUFFER, MIN_RR_TP1,
    NEWS_BLACKOUT,
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
_daily_ping_date = None

def is_session_active() -> bool:
    hour = datetime.now(timezone.utc).hour
    return (LONDON_START <= hour < LONDON_END) or (NY_START <= hour < NY_END)

def calculate_targets(entry, stop, direction):
    risk = abs(entry - stop)
    if direction == "bullish":
        return {
            "tp1": round(entry + risk * 5.0, 2),
            "tp2": round(entry + risk * 3.0, 2),
            "tp3": round(entry + risk * 1.5, 2),
        }
    return {
        "tp1": round(entry - risk * 5.0, 2),
        "tp2": round(entry - risk * 3.0, 2),
        "tp3": round(entry - risk * 1.5, 2),
    }

def _htf_bias_quality(d1, h4):
    """Prefer D1+H4 agree. Allow clean H4 only if D1 not opposite."""
    b1 = determine_bias(d1)
    b4 = determine_bias(h4)
    if b1 != "neutral" and b1 == b4:
        return b1, "D1+H4"
    if b4 != "neutral" and b1 != ("bearish" if b4 == "bullish" else "bullish"):
        # H4 clear, D1 not fighting
        if b1 == "neutral" or b1 == b4:
            return b4, "H4"
    return None, ""

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

    bias, src = _htf_bias_quality(d1, h4)
    if not bias:
        print("PA: no quality HTF bias")
        return None

    # Quality confirmation only: engulfing or pin (not weak impulse alone)
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

    # Strong body only if also with HTF and decent size
    if not confirmation and len(m15) >= 2:
        c = m15.iloc[-1]
        body = float(c["close"] - c["open"])
        rng = float(c["high"] - c["low"]) or 1
        if abs(body) >= 5 and abs(body) / rng >= 0.65:
            if bias == "bullish" and body > 0:
                confirmation = "15m strong body"
            elif bias == "bearish" and body < 0:
                confirmation = "15m strong body"

    if not confirmation:
        print("PA: no quality confirmation")
        return None

    structure = find_nearby_structure_level(m15, bias)
    if structure is None:
        structure = float(m15["low"].tail(25).min()) if bias == "bullish" else float(m15["high"].tail(25).max())

    price = float(m15["close"].iloc[-1])

    # Prefer entry zone toward structure (limit-style pullback area)
    if bias == "bullish":
        zone_mid = (price + structure) / 2 if structure < price else price
        el = round(min(structure + 2, zone_mid - 1), 2)
        eh = round(price + 0.5, 2)
        if el > eh:
            el, eh = round(price - 2, 2), round(price + 0.5, 2)
        stop = round(structure - XAU_SL_BUFFER, 2)
        if stop >= el:
            stop = round(el - XAU_SL_BUFFER, 2)
        direction = "BUY"
    else:
        zone_mid = (price + structure) / 2 if structure > price else price
        el = round(price - 0.5, 2)
        eh = round(max(structure - 2, zone_mid + 1), 2)
        if el > eh:
            el, eh = round(price - 0.5, 2), round(price + 2, 2)
        stop = round(structure + XAU_SL_BUFFER, 2)
        if stop <= eh:
            stop = round(eh + XAU_SL_BUFFER, 2)
        direction = "SELL"

    mid = (el + eh) / 2
    risk = abs(mid - stop)
    if risk < 8 or risk > 80:
        print(f"PA: risk out of band {risk:.1f}")
        return None

    targets = calculate_targets(mid, stop, bias)
    if abs(float(targets["tp3"]) - mid) / risk < MIN_RR_TP1:
        return None

    print(f"QUALITY PA {direction} {src} conf={confirmation}")

    return {
        "pair": "XAUUSD",
        "direction": direction,
        "entry_zone": f"{el}-{eh}",
        "stop_loss": str(stop),
        "tp1": str(targets["tp1"]),
        "tp2": str(targets["tp2"]),
        "tp3": str(targets["tp3"]),
    }

def _morning_daily_note():
    global _daily_ping_date
    today = datetime.now(timezone.utc).date()
    if _daily_ping_date == today:
        return
    hour = datetime.now(timezone.utc).hour
    if hour < 7 or hour > 10:
        return
    msg = (
        "☀️ QUALITY MODE\n"
        "⚡ Daily PA — clean HTF + confirmation\n"
        "🔥 Momentum — strong moves only\n"
        "🥇🥈 Event trains on news"
    )
    if send_message(msg):
        _daily_ping_date = today

def run_once():
    print(f"\n=== Run @ {datetime.now(timezone.utc).isoformat()} ===")
    try:
        _morning_daily_note()
    except Exception as e:
        print("daily note", e)

    if run_event_cycle:
        try:
            print("Events:", run_event_cycle())
        except Exception as e:
            print("Event error:", e)

    if run_momentum:
        try:
            run_momentum()
        except Exception as e:
            print("Momentum error:", e)

    signal = generate_signal()
    if signal is None:
        print("No quality PA this cycle")
        return
    if send_signal(signal):
        global signals_today
        signals_today += 1
        print("PA posted", signals_today)

if __name__ == "__main__":
    run_once()
