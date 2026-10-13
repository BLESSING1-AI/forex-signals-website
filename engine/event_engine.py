"""
Event Signal Engine
Pre-event + Post-event directional signals for high-impact news
(NFP, CPI, FOMC, PPI, Retail Sales, GDP, etc.)
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List

from event_calendar import get_events_in_window, fetch_upcoming_events
from data_fetcher import get_multi_timeframe_data
from structure import determine_bias, detect_engulfing, detect_pin_bar, find_nearby_structure_level
from telegram_poster import send_message
from config import XAU_SL_BUFFER, DEFAULT_RISK_PERCENT

# Simple daily guard so we don't spam the same event
_sent_event_keys = set()

def _event_key(event: Dict, kind: str) -> str:
    t = event["time"].strftime("%Y%m%d%H%M")
    return f"{kind}:{event['name'][:40]}:{t}"

def _format_event_signal(signal: Dict) -> str:
    direction = signal["direction"].upper()
    pair = signal["pair"]
    event_name = signal["event_name"]
    phase = signal["phase"]  # PRE or POST

    header = f"🚨 EVENT SIGNAL ({phase}): {direction} {pair} 🚨"

    text = f"""{header}

📰 Event: {event_name}
⏰ Release: {signal['event_time']}

📍 Entry Zone: {signal['entry_zone']}
🛑 Stop Loss: {signal['stop_loss']}

🎯 Take Profit 1: {signal['tp1']} (Partial + Move SL to BE)
🎯 Take Profit 2: {signal['tp2']}
🎯 Take Profit 3: {signal['tp3']}

📊 Context:
{signal.get('context', '')}
• Recommended Risk: {signal.get('risk', '1%')} per trade
• Event volatility is high — reduce size if needed

⚠️ Educational only. News can gap and spike. Manage risk."""
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

def generate_pre_event_signal(event: Dict) -> Optional[Dict]:
    """
    Pre-event directional bias using current HTF structure.
    We only send if there is a clear HTF bias so students have a plan before the number.
    """
    key = _event_key(event, "PRE")
    if key in _sent_event_keys:
        return None

    data = get_multi_timeframe_data()
    d1, h4, m15 = data.get("1d"), data.get("4h"), data.get("15m")
    if any(x is None or x.empty for x in [d1, h4, m15]):
        return None

    bias = determine_bias(d1)
    h4_bias = determine_bias(h4)
    if bias == "neutral" or bias != h4_bias:
        # No clear bias → still notify about the event but without forced direction
        return None

    price = float(m15["close"].iloc[-1])
    structure = find_nearby_structure_level(m15, bias)
    if structure is None:
        return None

    if bias == "bullish":
        direction = "BUY"
        entry_low = round(price - 2.0, 2)
        entry_high = round(price + 1.0, 2)
        stop = round(structure - XAU_SL_BUFFER - 10, 2)  # wider for news
    else:
        direction = "SELL"
        entry_low = round(price - 1.0, 2)
        entry_high = round(price + 2.0, 2)
        stop = round(structure + XAU_SL_BUFFER + 10, 2)

    entry_mid = (entry_low + entry_high) / 2
    targets = _calc_targets(entry_mid, stop, bias)

    mins = event.get("minutes_to_event", 0)
    context = (
        f"• PRE-EVENT bias from D1/H4 {bias} structure\n"
        f"• Event in ~{int(abs(mins))} minutes\n"
        f"• Expect high volatility — wait for post-release confirmation if unsure\n"
        f"• Forecast: {event.get('forecast')} | Previous: {event.get('previous')}"
    )

    signal = {
        "pair": "XAUUSD",
        "direction": direction,
        "entry_zone": f"{entry_low} - {entry_high}",
        "stop_loss": str(stop),
        "tp1": str(targets["tp1"]),
        "tp2": str(targets["tp2"]),
        "tp3": str(targets["tp3"]),
        "event_name": event["name"],
        "event_time": event["time"].strftime("%Y-%m-%d %H:%M UTC"),
        "phase": "PRE",
        "context": context,
        "risk": f"{DEFAULT_RISK_PERCENT}%",
    }
    return signal

def generate_post_event_signal(event: Dict) -> Optional[Dict]:
    """
    Post-event: look for immediate directional confirmation after the release.
    """
    key = _event_key(event, "POST")
    if key in _sent_event_keys:
        return None

    data = get_multi_timeframe_data()
    m15, m5 = data.get("15m"), data.get("5m")
    if m15 is None or m15.empty:
        return None

    # Prefer M5 reaction if available
    tf = m5 if m5 is not None and not m5.empty else m15
    engulf = detect_engulfing(tf)
    pin = detect_pin_bar(tf)

    direction_bias = None
    conf = None
    if engulf == "bullish" or pin == "bullish":
        direction_bias = "bullish"
        conf = engulf or pin
    elif engulf == "bearish" or pin == "bearish":
        direction_bias = "bearish"
        conf = engulf or pin

    if not direction_bias:
        return None

    price = float(tf["close"].iloc[-1])
    structure = find_nearby_structure_level(m15, direction_bias)
    if structure is None:
        return None

    if direction_bias == "bullish":
        direction = "BUY"
        entry_low = round(price - 1.5, 2)
        entry_high = round(price + 0.8, 2)
        stop = round(structure - XAU_SL_BUFFER, 2)
    else:
        direction = "SELL"
        entry_low = round(price - 0.8, 2)
        entry_high = round(price + 1.5, 2)
        stop = round(structure + XAU_SL_BUFFER, 2)

    entry_mid = (entry_low + entry_high) / 2
    targets = _calc_targets(entry_mid, stop, direction_bias)

    actual = event.get("actual")
    forecast = event.get("forecast")
    surprise_note = ""
    if actual is not None and forecast is not None:
        surprise_note = f"\n• Actual: {actual} vs Forecast: {forecast}"

    context = (
        f"• POST-EVENT reaction confirmed ({conf})\n"
        f"• Directional follow-through after {event['name']}"
        f"{surprise_note}\n"
        f"• Trade the reaction, not the prediction"
    )

    signal = {
        "pair": "XAUUSD",
        "direction": direction,
        "entry_zone": f"{entry_low} - {entry_high}",
        "stop_loss": str(stop),
        "tp1": str(targets["tp1"]),
        "tp2": str(targets["tp2"]),
        "tp3": str(targets["tp3"]),
        "event_name": event["name"],
        "event_time": event["time"].strftime("%Y-%m-%d %H:%M UTC"),
        "phase": "POST",
        "context": context,
        "risk": f"{DEFAULT_RISK_PERCENT}%",
    }
    return signal

def run_event_cycle() -> List[Dict]:
    """
    Main entry: check for pre and post event opportunities and post them.
    """
    posted = []
    window = get_events_in_window(minutes_before=120, minutes_after=45)

    if not window:
        # Also surface very near-term upcoming high-impact so channel stays informed
        upcoming = fetch_upcoming_events(hours_ahead=24)
        if upcoming:
            next_e = upcoming[0]
            mins = (next_e["time"] - datetime.now(timezone.utc)).total_seconds() / 60
            if 0 < mins < 180:
                # Soft heads-up only (not a full directional signal)
                msg = (
                    f"📅 HIGH IMPACT EVENT SOON\n\n"
                    f"📰 {next_e['name']}\n"
                    f"⏰ {next_e['time'].strftime('%Y-%m-%d %H:%M UTC')} "
                    f"(~{int(mins)} min)\n"
                    f"Forecast: {next_e.get('forecast')} | Previous: {next_e.get('previous')}\n\n"
                    f"Engine will look for PRE and POST directional setups around this release."
                )
                key = _event_key(next_e, "HEADS")
                if key not in _sent_event_keys:
                    if send_message(msg):
                        _sent_event_keys.add(key)
        return posted

    for event in window:
        mins = event.get("minutes_to_event", 0)

        # PRE window: 15–120 minutes before
        if 15 <= mins <= 120:
            sig = generate_pre_event_signal(event)
            if sig:
                text = _format_event_signal(sig)
                if send_message(text):
                    _sent_event_keys.add(_event_key(event, "PRE"))
                    posted.append(sig)
                    print(f"Posted PRE-EVENT signal for {event['name']}")

        # POST window: 0–45 minutes after
        if -45 <= mins <= 5:
            sig = generate_post_event_signal(event)
            if sig:
                text = _format_event_signal(sig)
                if send_message(text):
                    _sent_event_keys.add(_event_key(event, "POST"))
                    posted.append(sig)
                    print(f"Posted POST-EVENT signal for {event['name']}")

    return posted
