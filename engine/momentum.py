"""
Daily momentum scalps — members can grow accounts on quiet days too
Max from config · TP1 further · TP2 closer
"""
from datetime import datetime, timezone
from typing import Optional, Dict

from data_fetcher import get_multi_timeframe_data
from structure import determine_bias, detect_engulfing, detect_pin_bar
from telegram_poster import send_momentum
from config import LONDON_START, LONDON_END, NY_START, NY_END

try:
    from config import MAX_MOMENTUM_PER_DAY
except Exception:
    MAX_MOMENTUM_PER_DAY = 5

_last_mom_time = None
_mom_count_today = 0
_mom_date = None

def _session() -> bool:
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
    if not _session():
        return None

    now = datetime.now(timezone.utc)
    # 30 min cooldown so daily flow still feels active
    if _last_mom_time and (now - _last_mom_time).total_seconds() < 30 * 60:
        return None

    data = get_multi_timeframe_data()
    h4, m15, m5 = data.get("4h"), data.get("15m"), data.get("5m")
    if any(x is None or x.empty for x in [h4, m15]):
        return None

    h4_bias = determine_bias(h4)
    if h4_bias == "neutral":
        # soft: use M15 swing bias for daily flow
        h4_bias = determine_bias(m15)
        if h4_bias == "neutral":
            return None

    tf = m5 if m5 is not None and not m5.empty else m15
    if len(tf) < 4:
        return None

    engulf = detect_engulfing(tf)
    pin = detect_pin_bar(tf)
    c = tf.iloc[-1]
    body = float(c["close"] - c["open"])
    rng = float(c["high"] - c["low"]) or 1

    if h4_bias == "bullish" and (engulf == "bullish" or pin == "bullish" or (body > 0 and abs(body) / rng > 0.5)):
        direction = "BUY"
    elif h4_bias == "bearish" and (engulf == "bearish" or pin == "bearish" or (body < 0 and abs(body) / rng > 0.5)):
        direction = "SELL"
    else:
        return None

    recent = tf.tail(3)
    ups = sum(1 for _, r in recent.iterrows() if r["close"] > r["open"])
    downs = 3 - ups
    if direction == "BUY" and ups < 2:
        return None
    if direction == "SELL" and downs < 2:
        return None

    price = float(c["close"])
    if direction == "BUY":
        sl = round(float(tf["low"].tail(5).min()) - 3, 2)
        risk = abs(price - sl)
        if risk < 2 or risk > 30:
            return None
        tp1 = round(price + risk * 2.0, 2)
        tp2 = round(price + risk * 1.2, 2)
        el, eh = round(price - 0.5, 2), round(price + 0.4, 2)
    else:
        sl = round(float(tf["high"].tail(5).max()) + 3, 2)
        risk = abs(sl - price)
        if risk < 2 or risk > 30:
            return None
        tp1 = round(price - risk * 2.0, 2)
        tp2 = round(price - risk * 1.2, 2)
        el, eh = round(price - 0.4, 2), round(price + 0.5, 2)

    return {
        "direction": direction,
        "entry_zone": f"{el}-{eh}",
        "stop_loss": str(sl),
        "tp1": str(tp1),
        "tp2": str(tp2),
    }

def run_momentum() -> bool:
    global _last_mom_time, _mom_count_today
    sig = generate_momentum()
    if not sig:
        return False
    if send_momentum(sig):
        _last_mom_time = datetime.now(timezone.utc)
        _mom_count_today += 1
        print(f"Momentum {_mom_count_today}/{MAX_MOMENTUM_PER_DAY}")
        return True
    return False
