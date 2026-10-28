"""
Event trains — one message per event.
Train 1 ONLY before release (defensive).
Train 2 ONLY after release (confirmation).
"""
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Set

from event_calendar import fetch_upcoming_events
from data_fetcher import get_multi_timeframe_data
from structure import determine_bias, detect_engulfing, detect_pin_bar, find_nearby_structure_level
from telegram_poster import send_message
from config import XAU_SL_BUFFER
from state_store import load_sent, save_sent

SAST = timezone(timedelta(hours=2))
_sent: Set[str] = set()

PRIORITY = [
    "fomc", "fed interest", "interest rate decision", "powell", "press conference",
    "non-farm", "nonfarm", "nfp", "payroll",
    "cpi", "consumer price",
    "core pce", "pce",
    "gdp",
    "ppi",
    "retail sales",
    "unemployment",
]

def _priority(name: str) -> int:
    n = name.lower()
    for i, k in enumerate(PRIORITY):
        if k in n:
            return i
    return 80

def _is_primary(name: str) -> bool:
    return _priority(name) < 20

def _sast(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(SAST).strftime("%H:%M SAST")

def _sast_full(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(SAST).strftime("%a %d %b %H:%M SAST")

def _key(event: Dict, kind: str) -> str:
    return f"{kind}:{event['name'][:40]}:{event['time'].strftime('%Y%m%d%H%M')}"

def _gold(bias: str) -> str:
    return "BUY GOLD" if bias == "bullish" else "SELL GOLD"

def _already(k: str) -> bool:
    return k in _sent

def _mark(k: str) -> None:
    _sent.add(k)

def _htf_bias() -> Optional[str]:
    try:
        data = get_multi_timeframe_data("XAUUSD")
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
        # net fallback
        if h4 is not None and len(h4) >= 5:
            net = float(h4["close"].iloc[-1] - h4["close"].iloc[-5])
            if abs(net) >= 3:
                return "bullish" if net > 0 else "bearish"
    except Exception as e:
        print("htf bias", e)
    return None

def _levels(bias: str, price: float, structure: float, wide: bool = False) -> Dict:
    if wide:
        buf = max(XAU_SL_BUFFER + 35, 50)
        if bias == "bullish":
            el, eh = round(price - 0.5, 2), round(price + 2.0, 2)
            stop = round(min(structure, price) - buf, 2)
        else:
            el, eh = round(price - 2.0, 2), round(price + 0.5, 2)
            stop = round(max(structure, price) + buf, 2)
        mid = (el + eh) / 2
        risk = abs(mid - stop) or 1
        if bias == "bullish":
            t1 = round(mid + risk * 0.7, 2)
            t2 = round(mid + risk * 1.5, 2)
            t3 = round(mid + risk * 2.5, 2)
        else:
            t1 = round(mid - risk * 0.7, 2)
            t2 = round(mid - risk * 1.5, 2)
            t3 = round(mid - risk * 2.5, 2)
    else:
        buf = XAU_SL_BUFFER + 5
        if bias == "bullish":
            el, eh = round(price - 1.5, 2), round(price + 0.8, 2)
            stop = round(min(structure, price) - buf, 2)
        else:
            el, eh = round(price - 0.8, 2), round(price + 1.5, 2)
            stop = round(max(structure, price) + buf, 2)
        mid = (el + eh) / 2
        risk = abs(mid - stop) or 1
        if bias == "bullish":
            t1 = round(mid + risk * 1.5, 2)
            t2 = round(mid + risk * 3.0, 2)
            t3 = round(mid + risk * 5.0, 2)
        else:
            t1 = round(mid - risk * 1.5, 2)
            t2 = round(mid - risk * 3.0, 2)
            t3 = round(mid - risk * 5.0, 2)
    return {"zone": f"{el}-{eh}", "sl": str(stop), "tp1": str(t1), "tp2": str(t2), "tp3": str(t3)}

def _short_pre(event, bias, levels, mins, tag) -> str:
    return (
        f"🥇 TRAIN 1 {tag}\n"
        f"{_gold(bias)} · {event['name'][:40]}\n"
        f"Release {_sast(event['time'])} (~{int(abs(mins))}m)\n"
        f"In: {levels['zone']}\n"
        f"SL: {levels['sl']}\n"
        f"TP1: {levels['tp1']} | TP2: {levels['tp2']} | TP3: {levels['tp3']}\n"
        f"Risk 0.5% · Take TP1"
    )

def _short_post(event, bias, levels, conf) -> str:
    return (
        f"🥈 TRAIN 2 — RIDE IT\n"
        f"{_gold(bias)} · {event['name'][:40]}\n"
        f"Confirm: {conf}\n"
        f"In: {levels['zone']}\n"
        f"SL: {levels['sl']}\n"
        f"TP1: {levels['tp1']} | TP2: {levels['tp2']} | TP3: {levels['tp3']}\n"
        f"BE after TP1 · Risk 1%"
    )

def _announce_each_event_today() -> None:
    now = datetime.now(timezone.utc)
    sast_today = now.astimezone(SAST).date()
    try:
        upcoming = fetch_upcoming_events(hours_ahead=48)
    except Exception as e:
        print("calendar", e)
        return
    future = [e for e in upcoming if e["time"] > now + timedelta(minutes=5)]
    today_ev = [e for e in future if e["time"].astimezone(SAST).date() == sast_today]
    if not today_ev:
        prim = [e for e in future if _is_primary(e["name"])]
        if not prim:
            return
        today_ev = prim[:1]
    lean = _htf_bias()
    lean_txt = _gold(lean) if lean else "TBD closer to release"
    for e in sorted(today_ev, key=lambda x: x["time"]):
        k = _key(e, "NOTICE")
        if _already(k):
            continue
        name = e["name"]
        tag = "PRIMARY" if _is_primary(name) else "HIGH"
        msg = (
            f"📅 EVENT · {tag}\n"
            f"{name}\n"
            f"{_sast_full(e['time'])}\n"
            f"Lean: {lean_txt}\n"
            f"Train 1 ~30m before · Train 2 after confirm"
        )
        if send_message(msg):
            _mark(k)

def _any_pre_sent(event: Dict) -> bool:
    return any(
        _already(_key(event, t))
        for t in ("PRE30M", "PRE5M", "PRENOW")
    )

def generate_pre(event: Dict, tag: str) -> bool:
    k = _key(event, f"PRE{tag}")
    if _already(k) or _any_pre_sent(event):
        return False

    bias = _htf_bias()
    if not bias:
        print("No bias for pre", event.get("name"))
        return False

    data = get_multi_timeframe_data("XAUUSD")
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

    data = get_multi_timeframe_data("XAUUSD")
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
        _announce_each_event_today()
    except Exception as e:
        print("notice error", e)

    now = datetime.now(timezone.utc)
    try:
        upcoming = fetch_upcoming_events(hours_ahead=24)
    except Exception as e:
        print("upcoming fail", e)
        upcoming = []

    window = []
    for e in upcoming:
        mins = (e["time"] - now).total_seconds() / 60
        e["minutes_to_event"] = mins
        if -60 <= mins <= 50:
            window.append(e)

    print("Event window:", [(x["name"][:28], round(x["minutes_to_event"])) for x in window])

    seen = set()
    unique = []
    for e in window:
        k = f"{e['name'][:40]}:{e['time'].strftime('%Y%m%d%H%M')}"
        if k in seen:
            continue
        seen.add(k)
        unique.append(e)
    unique.sort(key=lambda e: e["time"])

    for event in unique:
        mins = float(event.get("minutes_to_event", 0))

        # TRAIN 1 — only BEFORE release
        if 15 <= mins <= 45:
            if generate_pre(event, "30M"):
                posted.append(f"PRE30:{event['name'][:20]}")
        if 2 <= mins <= 14:
            if generate_pre(event, "5M"):
                posted.append(f"PRE5:{event['name'][:20]}")
        # Force primary if still before and no pre yet
        if _is_primary(event["name"]) and 2 <= mins <= 45 and not _any_pre_sent(event):
            if generate_pre(event, "NOW"):
                posted.append(f"PRENOW:{event['name'][:20]}")

        # TRAIN 2 — only AFTER release (mins negative or 0..3)
        if -55 <= mins <= 3:
            if generate_post(event):
                posted.append(f"POST:{event['name'][:20]}")

    save_sent(_sent)
    print("Posted:", posted)
    return posted
