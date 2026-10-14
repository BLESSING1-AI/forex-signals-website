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

_sent_event_keys = set()

def _event_key(event: Dict, kind: str) -> str:
    t = event["time"].strftime("%Y%m%d%H%M")
    return f"{kind}:{event['name'][:40]}:{t}"

def _format_event_signal(signal: Dict) -> str:
    direction = signal["direction"].upper()
    pair = signal["pair"]
    event_name = signal["event_name"]
    phase = signal["phase"]

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
    key = _event_key(event, "PRE")
    if key in _sent_event_keys:
        return None

    data = get_multi_timeframe_data()
    d1, h4, m15 = data.get("1d"), data.get("4h"), data.get("15m")
    if any(x is None or x.empty for x in [d1, h4, m15]):
        return None

    bias = determine_bias(d1)
    h4_bias = determine_bias(h4)

    # Prefer full alignment; if D1 neutral but H4 clear, still allow PRE bias
    if bias == "neutral" and h4_bias != "neutral":
        bias = h4_bias
    elif bias == "neutral" or (h4_bias != "neutral" and bias != h4_bias):
        if h4_bias == "neutral":
            return None
        # conflict → skip forced direction
        if bias != h4_bias and bias != "neutral":
            return None

    if bias == "neutral":
        return None

    price = float(m15["close"].iloc[-1])
    structure = find_nearby_structure_level(m15, bias)
    if structure is None:
        # fallback: use recent swing from last 20 bars
        structure = float(m15["low"].tail(20).min()) if bias == "bullish" else float(m15["high"].tail(20).max())

    if bias == "bullish":
        direction = "BUY"
        entry_low = round(price - 2.0, 2)
        entry_high = round(price + 1.0, 2)
        stop = round(min(structure, price) - XAU_SL_BUFFER - 10, 2)
    else:
        direction = "SELL"
        entry_low = round(price - 1.0, 2)
        entry_high = round(price + 2.0, 2)
        stop = round(max(structure, price) + XAU_SL_BUFFER + 10, 2)

    entry_mid = (entry_low + entry_high) / 2
    targets = _calc_targets(entry_mid, stop, bias)

    mins = event.get("minutes_to_event", 0)
    context = (
        f"• PRE-EVENT bias from HTF {bias} structure\n"
        f"• Event in ~{int(abs(mins))} minutes\n"
        f"• Expect high volatility — prefer confirmation after release if unsure\n"
        f"• Forecast: {event.get('forecast')} | Previous: {event.get('previous')}"
    )

    return {
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
    if engulf == "bullish" or pin == "bullish":
        direction_bias = "bullish"
        conf = engulf or pin
    elif engulf == "bearish" or pin == "bearish":
        direction_bias = "bearish"
        conf = engulf or pin

    # Fallback: strong directional candle body after news
    if not direction_bias and len(tf) >= 1:
        c = tf.iloc[-1]
        body = c["close"] - c["open"]
        rng = c["high"] - c["low"]
        if rng > 0 and abs(body) / rng > 0.6:
            if body > 0:
                direction_bias = "bullish"
                conf = "strong bullish impulse"
            else:
                direction_bias = "bearish"
                conf = "strong bearish impulse"

    if not direction_bias:
        return None

    price = float(tf["close"].iloc[-1])
    structure = find_nearby_structure_level(m15, direction_bias)
    if structure is None:
        structure = float(m15["low"].tail(15).min()) if direction_bias == "bullish" else float(m15["high"].tail(15).max())

    if direction_bias == "bullish":
        direction = "BUY"
        entry_low = round(price - 1.5, 2)
        entry_high = round(price + 0.8, 2)
        stop = round(min(structure, price) - XAU_SL_BUFFER, 2)
    else:
        direction = "SELL"
        entry_low = round(price - 0.8, 2)
        entry_high = round(price + 1.5, 2)
        stop = round(max(structure, price) + XAU_SL_BUFFER, 2)

    entry_mid = (entry_low + entry_high) / 2
    targets = _calc_targets(entry_mid, stop, direction_bias)

    surprise_note = ""
    if event.get("actual") is not None and event.get("forecast") is not None:
        surprise_note = f"\n• Actual: {event.get('actual')} vs Forecast: {event.get('forecast')}"

    context = (
        f"• POST-EVENT reaction confirmed ({conf})\n"
        f"• Directional follow-through after {event['name']}"
        f"{surprise_note}\n"
        f"• Trade the reaction, not the prediction"
    )

    return {
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

def _post_daily_brief() -> None:
    """Post today's high-impact events once per day."""
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    key = f"BRIEF:{today}"
    if key in _sent_event_keys:
        return

    upcoming = fetch_upcoming_events(hours_ahead=36)
    today_events = []
    now = datetime.now(timezone.utc)
    for e in upcoming:
        if e["time"].date() == now.date() and e["time"] >= now - timedelta(hours=1):
            today_events.append(e)

    if not today_events:
        # still mark so we don't spam empty
        _sent_event_keys.add(key)
        return

    lines = ["📅 TODAY'S HIGH-IMPACT EVENTS (USD)\n"]
    for e in today_events[:8]:
        lines.append(
            f"• {e['time'].strftime('%H:%M UTC')} — {e['name']}\n"
            f"  Forecast: {e.get('forecast')} | Prev: {e.get('previous')}"
        )
    lines.append("\nEngine will post PRE and POST directional setups around these releases.")
    lines.append("Gold (XAUUSD) is primary focus.")

    if send_message("\n".join(lines)):
        _sent_event_keys.add(key)
        print("Posted daily event brief")

def run_event_cycle() -> List[Dict]:
    posted = []

    # Always try daily brief early in the UTC day / whenever engine runs
    try:
        _post_daily_brief()
    except Exception as e:
        print(f"Brief error: {e}")

    # Wider window for PRE (up to 4h before) and POST (up to 60m after)
    window = get_events_in_window(minutes_before=240, minutes_after=60)

    upcoming = fetch_upcoming_events(hours_ahead=24)

    # Heads-up for events within next 12 hours (not only 3h)
    if upcoming:
        next_e = upcoming[0]
        mins = (next_e["time"] - datetime.now(timezone.utc)).total_seconds() / 60
        if 0 < mins <= 12 * 60:
            key = _event_key(next_e, "HEADS")
            if key not in _sent_event_keys:
                msg = (
                    f"📅 HIGH IMPACT EVENT AHEAD\n\n"
                    f"📰 {next_e['name']}\n"
                    f"⏰ {next_e['time'].strftime('%Y-%m-%d %H:%M UTC')} "
                    f"(~{int(mins)} min / ~{mins/60:.1f}h)\n"
                    f"Forecast: {next_e.get('forecast')} | Previous: {next_e.get('previous')}\n\n"
                    f"Watch XAUUSD. PRE bias signal will post closer to the release.\n"
                    f"POST reaction signal will post after the number if confirmation prints."
                )
                if send_message(msg):
                    _sent_event_keys.add(key)
                    print(f"Posted heads-up for {next_e['name']}")

    for event in window:
        mins = event.get("minutes_to_event", 0)

        # PRE: 30 min to 4 hours before
        if 30 <= mins <= 240:
            sig = generate_pre_event_signal(event)
            if sig:
                text = _format_event_signal(sig)
                if send_message(text):
                    _sent_event_keys.add(_event_key(event, "PRE"))
                    posted.append(sig)
                    print(f"Posted PRE-EVENT signal for {event['name']}")

        # POST: up to 60 min after
        if -60 <= mins <= 10:
            sig = generate_post_event_signal(event)
            if sig:
                text = _format_event_signal(sig)
                if send_message(text):
                    _sent_event_keys.add(_event_key(event, "POST"))
                    posted.append(sig)
                    print(f"Posted POST-EVENT signal for {event['name']}")

    return posted
