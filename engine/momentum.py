"""
SERIOUS momentum only — big displacement + HTF alignment + continuation
Not micro noise. Risk 0.75% · TP1 further · TP2 closer
"""
from datetime import datetime, timezone
from typing import Optional, Dict

from data_fetcher import get_multi_timeframe_data
from structure import determine_bias, detect_engulfing, detect_pin_bar
from telegram_poster import send_momentum

try:
    from config import MAX_MOMENTUM_PER_DAY, LONDON_START, LONDON_END, NY_START, NY_END
except Exception:
    MAX_MOMENTUM_PER_DAY = 3
    LONDON_START, LONDON_END, NY_START, NY_END = 7, 16, 12, 21

_last_mom_time = None
_mom_count_today = 0
_mom_date = None

def _in_quality_session() -> bool:
    """London + NY only for serious momentum."""
    h = datetime.now(timezone.utc).hour
    return (LONDON_START <= h < LONDON_END) or (NY_START <= h < NY_END)

def generate_momentum() -> Optional[Dict]:
    global _last_mom_time, _mom_count_today, _mom_date

    today = datetime.now(timezone.utc).date()
    if _mom_date != today:
        _mom_date = today
        _mom_count_today = 0

    if _mom_count_today >= MAX_MOMENTUM_PER_DAY:
        return None

    wd = datetime.now(timezone.utc).weekday()
    if wd >= 5:
        return None

    if not _in_quality_session():
        print("Momentum: outside London/NY — skip")
        return None

    now = datetime.now(timezone.utc)
    # 45 min cooldown — quality over spam
    if _last_mom_time and (now - _last_mom_time).total_seconds() < 45 * 60:
        return None

    data = get_multi_timeframe_data()
    h4, m15, m5 = data.get("4h"), data.get("15m"), data.get("5m")
    if m15 is None or m15.empty or h4 is None or h4.empty:
        return None

    tf = m5 if m5 is not None and not m5.empty and len(m5) >= 8 else m15
    if len(tf) < 8:
        return None

    def displacement(bars: int):
        chunk = tf.tail(bars)
        net = float(chunk["close"].iloc[-1] - chunk["open"].iloc[0])
        hi = float(chunk["high"].max())
        lo = float(chunk["low"].min())
        return net, hi - lo

    net3, rng3 = displacement(3)
    net5, rng5 = displacement(5)
    net8, rng8 = displacement(8)

    # SERIOUS thresholds (gold points) — ignore small noise
    strong_up = (net3 >= 12 and net5 >= 15) or net5 >= 22 or net8 >= 30
    strong_down = (net3 <= -12 and net5 <= -15) or net5 <= -22 or net8 <= -30

    if not strong_up and not strong_down:
        print(f"Momentum: weak move net3={net3:.1f} net5={net5:.1f} net8={net8:.1f}")
        return None

    direction = "BUY" if strong_up else "SELL"

    # Must align with H4 bias (or strong M15 structure)
    h4_bias = determine_bias(h4)
    m15_bias = determine_bias(m15)
    bias_ok = (
        (direction == "BUY" and h4_bias == "bullish")
        or (direction == "SELL" and h4_bias == "bearish")
        or (direction == "BUY" and m15_bias == "bullish" and h4_bias != "bearish")
        or (direction == "SELL" and m15_bias == "bearish" and h4_bias != "bullish")
    )
    if not bias_ok:
        print(f"Momentum: no HTF align dir={direction} h4={h4_bias} m15={m15_bias}")
        return None

    # Continuation: last candle still with the move (not exhausted reversal)
    c = tf.iloc[-1]
    body = float(c["close"] - c["open"])
    if direction == "BUY" and body < -1.5:
        print("Momentum: last candle against BUY")
        return None
    if direction == "SELL" and body > 1.5:
        print("Momentum: last candle against SELL")
        return None

    # Prefer impulse / engulfing / pin in direction
    engulf = detect_engulfing(tf)
    pin = detect_pin_bar(tf)
    conf = None
    if direction == "BUY" and (engulf == "bullish" or pin == "bullish"):
        conf = engulf or pin
    elif direction == "SELL" and (engulf == "bearish" or pin == "bearish"):
        conf = engulf or pin
    elif abs(body) >= 3:
        conf = "impulse"
    else:
        # still allow pure strong displacement if range expansion is real
        if rng5 >= 18:
            conf = "range expansion"
        else:
            print("Momentum: no candle confirmation")
            return None

    price = float(c["close"])

    if direction == "BUY":
        swing_sl = float(tf["low"].tail(8).min()) - 5
        sl = round(min(swing_sl, price - 12), 2)
        risk = abs(price - sl)
        if risk < 8:
            sl = round(price - 12, 2)
            risk = 12
        if risk > 35:
            sl = round(price - 28, 2)
            risk = abs(price - sl)
        tp1 = round(price + risk * 2.2, 2)
        tp2 = round(price + risk * 1.3, 2)
        el, eh = round(price - 0.8, 2), round(price + 0.6, 2)
    else:
        swing_sl = float(tf["high"].tail(8).max()) + 5
        sl = round(max(swing_sl, price + 12), 2)
        risk = abs(sl - price)
        if risk < 8:
            sl = round(price + 12, 2)
            risk = 12
        if risk > 35:
            sl = round(price + 28, 2)
            risk = abs(sl - price)
        tp1 = round(price - risk * 2.2, 2)
        tp2 = round(price - risk * 1.3, 2)
        el, eh = round(price - 0.6, 2), round(price + 0.8, 2)

    print(f"QUALITY MOMENTUM {direction} net5={net5:.1f} conf={conf} h4={h4_bias}")

    return {
        "direction": direction,
        "entry_zone": f"{el}-{eh}",
        "stop_loss": str(sl),
        "tp1": str(tp1),
        "tp2": str(tp2),
        "note": conf,
    }

def run_momentum() -> bool:
    global _last_mom_time, _mom_count_today
    sig = generate_momentum()
    if not sig:
        return False
    if send_momentum(sig):
        _last_mom_time = datetime.now(timezone.utc)
        _mom_count_today += 1
        print(f"Momentum posted {_mom_count_today}/{MAX_MOMENTUM_PER_DAY}")
        return True
    return False
