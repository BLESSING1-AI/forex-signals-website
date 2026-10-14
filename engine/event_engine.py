"""
Event Signal Engine
SAST times • Buy Gold / Sell Gold language
Train 1: ~30 min before + final few minutes before
Train 2: after event confirmation (ride the move)
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List

from event_calendar import get_events_in_window, fetch_upcoming_events
from data_fetcher import get_multi_timeframe_data
from structure import determine_bias, detect_engulfing, detect_pin_bar, find_nearby_structure_level
from telegram_poster import send_message
from config import XAU_SL_BUFFER, DEFAULT_RISK_PERCENT

SAST = timezone(timedelta(hours=2))
_sent_event_keys = set()

def _sast(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(SAST).strftime("%Y-%m-%d %H:%M SAST")

def _event_key(event: Dict, kind: str) -> str:
    t = event["time"].strftime("%Y%m%d%H%M")
    return f"{kind}:{event['name'][:40]}:{t}"

def _gold_direction(bias: str) -> str:
    return "BUY GOLD" if bias == "bullish" else "SELL GOLD"

def _format_event_signal(signal: Dict) -> str:
    dir_label = signal["direction_label"]  # BUY GOLD / SELL GOLD
    phase = signal["phase"]
    train = signal.get("train", "")

    header = f"🚨 {dir_label} — EVENT {phase} {train} 🚨".strip()

    text = f"""{header}

📰 Event: {signal['event_name']}
⏰ Release: {signal['event_time_sast']}

📍 Entry Zone: {signal['entry_zone']}
🛑 Stop Loss: {signal['stop_loss']}

🎯 TP1: {signal['tp1']} (partial + move SL to BE)
🎯 TP2: {signal['tp2']}
🎯 TP3: {signal['tp3']}

📊 Context:
{signal.get('context', '')}
• Risk: {signal.get('risk', '1%')} max
• Pair focus: XAUUSD (Gold)

⚠️ Educational only. News spikes fast — size down."""
    return text.strip()

def _calc_targets(entry: float, stop: float, direction: str) -> Dict:
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

def _build_levels(bias: str, price: float, structure: float) -> Dict:
    if bias == "bullish":
        entry_low = round(price - 1.5, 2)
        entry_high = round(price + 0.8, 2)
        stop = round(min(structure, price) - XAU_SL_BUFFER - 8, 2)
        direction = "bullish"
    else:
        entry_low = round(price - 0.8, 2)
        entry_high = round(price + 1.5, 2)
        stop = round(max(structure, price) + XAU_SL_BUFFER + 8, 2)
        direction = "bearish"
    entry_mid = (entry_low + entry_high) / 2
    targets = _calc_targets(entry_mid, stop, direction)
    return {
        "entry_zone": f"{entry_low} - {entry_high}",
        "stop_loss": str(stop),
        "tp1": str(targets["tp1"]),
        "tp2": str(targets["tp2"]),
        "tp3": str(targets["tp3"]),
        "direction": direction,
    }

def _htf_bias() -> Optional[str]:
    data = get_multi_timeframe_data()
    d1, h4 = data.get("1d"), data.get("4h")
    if d1 is None or d1.empty or h4 is None or h4.empty:
        return None
    b1 = determine_bias(d1)
    b4 = determine_bias(h4)
    if b1 != "neutral" and b1 == b4:
        return b1
    if b4 != "neutral":
        return b4
    if b1 != "neutral":
        return b1
    return None

def generate_pre_event_signal(event: Dict, train: str) -> Optional[Dict]:
    kind = f"PRE{train}"
    key = _event_key(event, kind)
    if key in _sent_event_keys:
        return None

    bias = _htf_bias()
    if not bias:
        return None

    data = get_multi_timeframe_data()
    m15 = data.get("15m")
    if m15 is None or m15.empty:
        return None

    price = float(m15["close"].iloc[-1])
    structure = find_nearby_structure_level(m15, bias)
    if structure is None:
        structure = float(m15["low"].tail(20).min()) if bias == "bullish" else float(m15["high"].tail(20).max())

    levels = _build_levels(bias, price, structure)
    mins = event.get("minutes_to_event", 0)

    if train == "30M":
        train_label = "(30 MIN BEFORE)"
        note = "Primary PRE plan — levels to work with into the release."
    else:
        train_label = "(FINAL — FEW MIN BEFORE)"
        note = "Final PRE alert. Prefer waiting for POST confirmation if price is messy."

    context = (
        f"• {note}\n"
        f"• HTF structure bias: {bias.upper()}\n"
        f"• ~{int(abs(mins))} minutes to release\n"
        f"• Forecast: {event.get('forecast')} | Previous: {event.get('previous')}\n"
        f"• After the number: wait for Train 2 (confirmation) to ride the move"
    )

    return {
        "direction_label": _gold_direction(bias),
        "direction": levels["direction"],
        "entry_zone": levels["entry_zone"],
        "stop_loss": levels["stop_loss"],
        "tp1": levels["tp1"],
        "tp2": levels["tp2"],
        "tp3": levels["tp3"],
        "event_name": event["name"],
        "event_time_sast": _sast(event["time"]),
        "phase": "PRE",
        "train": train_label,
        "context": context,
        "risk": f"{DEFAULT_RISK_PERCENT}%",
        "_key": key,
    }

def generate_post_event_signal(event: Dict) -> Optional[Dict]:
    key = _event_key(event, "POST")
    if key in _sent_event_keys:
        return None

    data = get_multi_timeframe_data()
    m15, m5 = data.get("15m"), data.get("5m")
    if m15 is None or m15.empty:
        return None

    tf = m5 if m5 is not None and not m5.empty else m15
    engulf = detect_engulfing(tf)
    pin = detect_pin_bar(tf)

    direction_bias = None
    conf = None
    if engulf in ("bullish", "bearish"):
        direction_bias, conf = engulf, f"{engulf} engulfing"
    elif pin in ("bullish", "bearish"):
        direction_bias, conf = pin, f"{pin} pin bar"

    if not direction_bias and len(tf) >= 1:
        c = tf.iloc[-1]
        body = float(c["close"] - c["open"])
        rng = float(c["high"] - c["low"])
        if rng > 0 and abs(body) / rng >= 0.55:
            direction_bias = "bullish" if body > 0 else "bearish"
            conf = "strong impulse candle"

    if not direction_bias:
        return None

    price = float(tf["close"].iloc[-1])
    structure = find_nearby_structure_level(m15, direction_bias)
    if structure is None:
        structure = float(m15["low"].tail(15).min()) if direction_bias == "bullish" else float(m15["high"].tail(15).max())

    levels = _build_levels(direction_bias, price, structure)

    surprise = ""
    if event.get("actual") is not None:
        surprise = f"\n• Actual: {event.get('actual')} | Forecast: {event.get('forecast')} | Prev: {event.get('previous')}"

    context = (
        f"• TRAIN 2 — confirmation after the release\n"
        f"• Trigger: {conf}\n"
        f"• Ride the reaction with the market{surprise}\n"
        f"• Move SL to BE after TP1"
    )

    return {
        "direction_label": _gold_direction(direction_bias),
        "direction": levels["direction"],
        "entry_zone": levels["entry_zone"],
        "stop_loss": levels["stop_loss"],
        "tp1": levels["tp1"],
        "tp2": levels["tp2"],
        "tp3": levels["tp3"],
        "event_name": event["name"],
        "event_time_sast": _sast(event["time"]),
        "phase": "POST",
        "train": "(TRAIN 2 — RIDE THE MOVE)",
        "context": context,
        "risk": f"{DEFAULT_RISK_PERCENT}%",
        "_key": key,
    }

def _post_daily_brief() -> None:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    key = f"BRIEF:{today}"
    if key in _sent_event_keys:
        return

    upcoming = fetch_upcoming_events(hours_ahead=36)
    now = datetime.now(timezone.utc)
    today_events = [e for e in upcoming if e["time"].date() == now.date() and e["time"] >= now - timedelta(hours=1)]

    if not today_events:
        _sent_event_keys.add(key)
        return

    lines = ["📅 TODAY'S HIGH-IMPACT EVENTS (times in SAST)\n"]
    for e in today_events[:8]:
        lines.append(
            f"• {_sast(e['time'])} — {e['name']}\n"
            f"  Forecast: {e.get('forecast')} | Prev: {e.get('previous')}"
        )
    lines.append("\nTrain 1: Buy/Sell Gold ~30 min before (+ final alert few min before)")
    lines.append("Train 2: confirmation after release — ride the move")

    if send_message("\n".join(lines)):
        _sent_event_keys.add(key)

def run_event_cycle() -> List[Dict]:
    posted = []
    try:
        _post_daily_brief()
    except Exception as e:
        print("Brief error:", e)

    window = get_events_in_window(minutes_before=45, minutes_after=60)
    upcoming = fetch_upcoming_events(hours_ahead=24)

    # Heads-up earlier in the day
    if upcoming:
        next_e = upcoming[0]
        mins = (next_e["time"] - datetime.now(timezone.utc)).total_seconds() / 60
        if 45 < mins <= 12 * 60:
            key = _event_key(next_e, "HEADS")
            if key not in _sent_event_keys:
                bias = _htf_bias() or "mixed"
                lean = _gold_direction(bias) if bias in ("bullish", "bearish") else "NO CLEAR HTF BIAS YET"
                msg = (
                    f"📅 HIGH IMPACT EVENT AHEAD\n\n"
                    f"📰 {next_e['name']}\n"
                    f"⏰ {_sast(next_e['time'])} (~{int(mins)} min)\n"
                    f"Forecast: {next_e.get('forecast')} | Previous: {next_e.get('previous')}\n\n"
                    f"Current structure lean: {lean}\n\n"
                    f"Train 1 (~30 min before): directional Buy/Sell Gold plan\n"
                    f"Train 2 (after print): confirmation to ride the move"
                )
                if send_message(msg):
                    _sent_event_keys.add(key)

    for event in window:
        mins = event.get("minutes_to_event", 0)

        # Train 1a — about 30 minutes before (25–35 min)
        if 25 <= mins <= 35:
            sig = generate_pre_event_signal(event, "30M")
            if sig:
                if send_message(_format_event_signal(sig)):
                    _sent_event_keys.add(sig["_key"])
                    posted.append(sig)
                    print("Posted PRE 30M", event["name"])

        # Train 1b — few minutes before (3–8 min)
        if 3 <= mins <= 8:
            sig = generate_pre_event_signal(event, "5M")
            if sig:
                if send_message(_format_event_signal(sig)):
                    _sent_event_keys.add(sig["_key"])
                    posted.append(sig)
                    print("Posted PRE 5M", event["name"])

        # Train 2 — after event confirmation
        if -60 <= mins <= 8:
            sig = generate_post_event_signal(event)
            if sig:
                if send_message(_format_event_signal(sig)):
                    _sent_event_keys.add(sig["_key"])
                    posted.append(sig)
                    print("Posted POST", event["name"])

    return posted
