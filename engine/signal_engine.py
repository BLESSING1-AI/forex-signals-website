"""
Quality daily PA + events + momentum
Guarantee: at least 1 gold signal per trading day (HTF lean fallback)
TP: TP1 furthest (5R) · TP2 (3R) · TP3 closest (1.5R)
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
from state_store import signals_posted_today, mark_signal_posted, load_sent, save_sent

try:
    from event_engine import run_event_cycle
except Exception:
    run_event_cycle = None

try:
    from momentum import run_momentum
except Exception:
    run_momentum = None

def is_session_active() -> bool:
    hour = datetime.now(timezone.utc).hour
    return (LONDON_START <= hour < LONDON_END) or (NY_START <= hour < NY_END)

def is_weekday() -> bool:
    return datetime.now(timezone.utc).weekday() < 5

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
    b1 = determine_bias(d1)
    b4 = determine_bias(h4)
    if b1 != "neutral" and b1 == b4:
        return b1, "D1+H4"
    if b4 != "neutral" and b1 != ("bearish" if b4 == "bullish" else "bullish"):
        if b1 == "neutral" or b1 == b4:
            return b4, "H4"
    return None, ""

def _htf_bias_any(d1, h4, m15):
    """Fallback lean — still needs a clear direction."""
    b = _htf_bias_quality(d1, h4)
    if b[0]:
        return b
    b4 = determine_bias(h4)
    if b4 != "neutral":
        return b4, "H4 lean"
    b15 = determine_bias(m15)
    if b15 != "neutral":
        return b15, "M15 lean"
    return None, ""

def _build_levels(bias, price, structure):
    if bias == "bullish":
        el = round(min(structure + 2, price - 1.5), 2)
        eh = round(price + 0.5, 2)
        if el > eh:
            el, eh = round(price - 2, 2), round(price + 0.5, 2)
        stop = round(structure - XAU_SL_BUFFER, 2)
        if stop >= el:
            stop = round(el - XAU_SL_BUFFER, 2)
        direction = "BUY"
    else:
        el = round(price - 0.5, 2)
        eh = round(max(structure - 2, price + 1.5), 2)
        if el > eh:
            el, eh = round(price - 0.5, 2), round(price + 2, 2)
        stop = round(structure + XAU_SL_BUFFER, 2)
        if stop <= eh:
            stop = round(eh + XAU_SL_BUFFER, 2)
        direction = "SELL"

    mid = (el + eh) / 2
    risk = abs(mid - stop)
    if risk < 6:
        return None
    if risk > 90:
        # tighten extreme SL
        if direction == "BUY":
            stop = round(mid - 40, 2)
        else:
            stop = round(mid + 40, 2)
        risk = abs(mid - stop)

    targets = calculate_targets(mid, stop, bias)
    return {
        "pair": "XAUUSD",
        "direction": direction,
        "entry_zone": f"{el}-{eh}",
        "stop_loss": str(stop),
        "tp1": str(targets["tp1"]),
        "tp2": str(targets["tp2"]),
        "tp3": str(targets["tp3"]),
    }

def generate_signal():
    """High-quality PA when confirmation is present."""
    if signals_posted_today() >= MAX_SIGNALS_PER_DAY or NEWS_BLACKOUT or not is_session_active():
        return None

    data = get_multi_timeframe_data()
    d1, h4, m15, m5 = data.get("1d"), data.get("4h"), data.get("15m"), data.get("5m")
    if any(x is None or x.empty for x in [d1, h4, m15]):
        return None

    bias, src = _htf_bias_quality(d1, h4)
    if not bias:
        print("PA: no quality HTF bias")
        return None

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
    sig = _build_levels(bias, price, structure)
    if not sig:
        return None
    if abs(float(sig["tp3"]) - (sum(map(float, sig["entry_zone"].split("-"))) / 2)) / abs(float(sig["stop_loss"]) - (sum(map(float, sig["entry_zone"].split("-"))) / 2)) < MIN_RR_TP1:
        return None

    sig["label"] = "Quality PA"
    print(f"QUALITY PA {sig['direction']} {src} conf={confirmation}")
    return sig

def generate_daily_must():
    """
    At least one signal per trading day.
    Fires once if nothing posted yet, from late London (~11 UTC) through NY.
    Uses HTF lean + structure — not random noise.
    """
    if not is_weekday() or NEWS_BLACKOUT:
        return None
    if signals_posted_today() >= 1:
        return None

    hour = datetime.now(timezone.utc).hour
    # Wait for some London structure, then ensure a signal by end of NY
    if hour < 11 or hour >= 21:
        print("Daily must: waiting for 11–21 UTC window")
        return None

    # Once-per-day key in sent state
    today = datetime.now(timezone.utc).date().isoformat()
    k = f"DAILY_MUST:{today}"
    sent = load_sent()
    if k in sent:
        return None

    data = get_multi_timeframe_data()
    d1, h4, m15 = data.get("1d"), data.get("4h"), data.get("15m")
    if any(x is None or x.empty for x in [d1, h4, m15]):
        return None

    bias, src = _htf_bias_any(d1, h4, m15)
    if not bias:
        # Last resort: close vs open of last 8 H4 bars
        last = h4.tail(8)
        net = float(last["close"].iloc[-1] - last["open"].iloc[0])
        if abs(net) < 8:
            print("Daily must: no lean")
            return None
        bias = "bullish" if net > 0 else "bearish"
        src = "H4 net"

    structure = find_nearby_structure_level(m15, bias)
    if structure is None:
        structure = float(m15["low"].tail(30).min()) if bias == "bullish" else float(m15["high"].tail(30).max())

    price = float(m15["close"].iloc[-1])
    sig = _build_levels(bias, price, structure)
    if not sig:
        return None

    sig["label"] = "Daily lean"
    sig["_state_key"] = k
    print(f"DAILY MUST {sig['direction']} {src}")
    return sig

def run_once():
    print(f"\n=== Run @ {datetime.now(timezone.utc).isoformat()} ===")
    print("Signals already today:", signals_posted_today())

    if run_event_cycle:
        try:
            print("Events:", run_event_cycle())
        except Exception as e:
            print("Event error:", e)

    mom_ok = False
    if run_momentum:
        try:
            mom_ok = bool(run_momentum())
            if mom_ok:
                mark_signal_posted()
        except Exception as e:
            print("Momentum error:", e)

    signal = generate_signal()
    if signal is None:
        signal = generate_daily_must()

    if signal is None:
        print("No PA / daily must this cycle")
        return

    if send_signal(signal):
        mark_signal_posted()
        k = signal.get("_state_key")
        if k:
            sent = load_sent()
            sent.add(k)
            save_sent(sent)
        print("Posted", signal.get("label"), signal["direction"], "total today", signals_posted_today())

if __name__ == "__main__":
    run_once()
