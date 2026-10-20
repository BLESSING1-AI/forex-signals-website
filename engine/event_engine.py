"""
Event trains — no spam
- Once per day: morning notice for today's / next high-impact
- Train 1 ~30m before (plan)
- Few minutes before (final reminder + plan)
- Train 2 after confirm (once)
"""
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Set

from event_calendar import get_events_in_window, fetch_upcoming_events
from data_fetcher import get_multi_timeframe_data
from structure import determine_bias, detect_engulfing, detect_pin_bar, find_nearby_structure_level
from telegram_poster import send_message
from config import XAU_SL_BUFFER
from state_store import load_sent, save_sent

SAST = timezone(timedelta(hours=2))
_sent: Set[str] = set()

def _sast(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(SAST).strftime("%H:%M SAST")

def _sast_full(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(SAST).strftime("%a %d %b %H:%M SAST")

def _key(event: Dict, kind: str) -> str:
    return f"{kind}:{event['name'][:30]}:{event['time'].strftime('%Y%m%d%H%M')}"

def _gold(bias: str) -> str:
    return "BUY GOLD" if bias == "bullish" else "SELL GOLD"

def _already(k: str) -> bool:
    return k in _sent

def _mark(k: str) -> None:
    _sent.add(k)

def _htf_bias() -> Optional[str]:
    data = get_multi_timeframe_data()
    d1, h4 = data.get("1d"), data.get("4h")
    if d1 is None or d1.empty or h4 is None or h4.empty:
        return None
    b1, b4 = determine_bias(d1), determine_bias(h4)
    if b1 != "neutral" and b1 == b4:
        return b1
    if b4 != "neutral":
        return b4
    if b1 != "neutral":
        return b1
    return None

def _levels(bias: str, price: float, structure: float, wide: bool = False) -> Dict:
    buf = XAU_SL_BUFFER + (10 if wide else 0)
    if bias == "bullish":
        el, eh = round(price - 1.5, 2), round(price + 0.8, 2)
        stop = round(min(structure, price) - buf, 2)
    else:
        el, eh = round(price - 0.8, 2), round(price + 1.5, 2)
        stop = round(max(structure, price) + buf, 2)
    mid = (el + eh) / 2
    risk = abs(mid - stop)
    if bias == "bullish":
        t1 = round(mid + risk * 5.0, 2)
        t2 = round(mid + risk * 3.0, 2)
        t3 = round(mid + risk * 1.5, 2)
    else:
        t1 = round(mid - risk * 5.0, 2)
        t2 = round(mid - risk * 3.0, 2)
        t3 = round(mid - risk * 1.5, 2)
    return {"zone": f"{el}-{eh}", "sl": str(stop), "tp1": str(t1), "tp2": str(t2), "tp3": str(t3)}

def _short_pre(event, bias, levels, mins, tag) -> str:
    return (
        f"🥇 TRAIN 1 {tag}\n"
        f"{_gold(bias)} · {event['name'][:40]}\n"
        f"Release {_sast(event['time'])} (~{int(abs(mins))}m)\n"
        f"In: {levels['zone']}\n"
        f"SL: {levels['sl']}\n"
        f"TP1: {levels['tp1']} | TP2: {levels['tp2']} | TP3: {levels['tp3']}\n"
        f"Risk 1% · Wait Train 2 if messy"
    )

def _short_post(event, bias, levels, conf) -> str:
    return (
        f"🥈 TRAIN 2 — RIDE IT\n"
        f"{_gold(bias)} · {event['name'][:40]}\n"
        f"Confirm: {conf}\n"
        f"In: {levels['zone']}\n"
        f"SL: {levels['sl']}\n"
        f"TP1: {levels['tp1']} | TP2: {levels['tp2']} | TP3: {levels['tp3']}\n"
        f"BE after TP3 · Risk 1%"
    )

def _morning_window() -> bool:
    """Once-daily slot: 07:00–07:20 SAST (05:00–05:20 UTC)."""
    now = datetime.now(timezone.utc)
    sast_now = now.astimezone(SAST)
    return sast_now.hour == 7 and sast_now.minute < 20

def _announce_once_today() -> None:
    """
    One message per calendar day (SAST) about today's high-impact cluster,
    or tomorrow's if nothing left today.
    Only fires in the morning window + state key prevents repeats.
    """
    if not _morning_window():
        return

    now = datetime.now(timezone.utc)
    sast_today = now.astimezone(SAST).date()
    day_key = f"DAILY_NOTICE:{sast_today.isoformat()}"
    if _already(day_key):
        return

    upcoming = fetch_upcoming_events(hours_ahead=48)
    future = [e for e in upcoming if e["time"] > now + timedelta(minutes=10)]
    if not future:
        _mark(day_key)
        return

    # Prefer events on this SAST day; else next day
    today_ev = [e for e in future if e["time"].astimezone(SAST).date() == sast_today]
    pool = today_ev if today_ev else future
    first = pool[0]
    cluster = [e for e in pool if abs((e["time"] - first["time"]).total_seconds()) < 3600]

    names = []
    seen = set()
    for e in cluster[:6]:
        n = e["name"]
        if n not in seen:
            seen.add(n)
            names.append(n)

    lean = _htf_bias()
    lean_txt = _gold(lean) if lean else "TBD closer to release"

    when_label = "TODAY" if first["time"].astimezone(SAST).date() == sast_today else "TOMORROW"

    msg = (
        f"📅 {when_label}'S HIGH IMPACT\n"
        f"{_sast_full(first['time'])}\n"
        + "\n".join(f"• {n}" for n in names) +
        f"\nLean: {lean_txt}\n"
        f"Train 1 ~30m before · final alert a few min before"
    )
    if send_message(msg):
        _mark(day_key)
        print("Daily event notice sent")

def generate_pre(event: Dict, tag: str) -> bool:
    k = _key(event, f"PRE{tag}")
    if _already(k):
        return False
    bias = _htf_bias()
    if not bias:
        return False
    data = get_multi_timeframe_data()
    m15 = data.get("15m")
    if m15 is None or m15.empty:
        return False
    price = float(m15["close"].iloc[-1])
    structure = find_nearby_structure_level(m15, bias)
    if structure is None:
        structure = float(m15["low"].tail(20).min()) if bias == "bullish" else float(m15["high"].tail(20).max())
    levels = _levels(bias, price, structure, wide=True)
    mins = event.get("minutes_to_event", 0)
    if send_message(_short_pre(event, bias, levels, mins, tag)):
        _mark(k)
        return True
    return False

def generate_post(event: Dict) -> bool:
    k = _key(event, "POST")
    if _already(k):
        return False

    data = get_multi_timeframe_data()
    m15, m5 = data.get("15m"), data.get("5m")
    if m15 is None or m15.empty:
        return False

    tf = m5 if m5 is not None and not m5.empty else m15
    bias = None
    conf = None

    engulf = detect_engulfing(tf)
    pin = detect_pin_bar(tf)
    if engulf in ("bullish", "bearish"):
        bias, conf = engulf, engulf
    elif pin in ("bullish", "bearish"):
        bias, conf = pin, f"{pin} pin"

    if not bias and len(tf) >= 3:
        c0, c2 = tf.iloc[-1], tf.iloc[-3]
        net = float(c0["close"] - c2["open"])
        body = float(c0["close"] - c0["open"])
        rng = float(c0["high"] - c0["low"]) or 1
        if abs(net) > 3 or abs(body) / rng >= 0.45:
            bias = "bullish" if (net > 0 or body > 0) else "bearish"
            conf = "impulse"

    if not bias and len(tf) >= 1:
        c = tf.iloc[-1]
        body = float(c["close"] - c["open"])
        if abs(body) >= 1.5:
            bias = "bullish" if body > 0 else "bearish"
            conf = "candle"

    if not bias:
        return False

    price = float(tf["close"].iloc[-1])
    structure = find_nearby_structure_level(m15, bias)
    if structure is None:
        structure = float(m15["low"].tail(12).min()) if bias == "bullish" else float(m15["high"].tail(12).max())
    levels = _levels(bias, price, structure, wide=False)
    if send_message(_short_post(event, bias, levels, conf)):
        _mark(k)
        return True
    return False

def run_event_cycle() -> List[str]:
    global _sent
    _sent = load_sent()
    posted = []

    try:
        _announce_once_today()
    except Exception as e:
        print("daily notice error", e)

    window = get_events_in_window(minutes_before=40, minutes_after=45)
    seen_slot = set()
    unique = []
    for e in window:
        slot = e["time"].strftime("%Y%m%d%H%M")
        if slot in seen_slot:
            continue
        seen_slot.add(slot)
        unique.append(e)

    for event in unique:
        mins = event.get("minutes_to_event", 0)

        # ~30 min before — once (state key)
        if 25 <= mins <= 35 and generate_pre(event, "30M"):
            posted.append("PRE30")

        # few minutes before — once
        if 3 <= mins <= 9 and generate_pre(event, "5M"):
            posted.append("PRE5")

        # Train 2 — once only (state key), shortly after release
        if -40 <= mins <= 10 and generate_post(event):
            posted.append("POST")

    save_sent(_sent)
    return posted
