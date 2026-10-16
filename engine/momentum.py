"""
Momentum scalps — catches BIG moves, not only perfect candles
Risk 0.5% · TP1 further · TP2 closer
"""
from datetime import datetime, timezone
from typing import Optional, Dict

from data_fetcher import get_multi_timeframe_data
from structure import determine_bias, detect_engulfing, detect_pin_bar
from telegram_poster import send_momentum

try:
    from config import MAX_MOMENTUM_PER_DAY
except Exception:
    MAX_MOMENTUM_PER_DAY = 5

_last_mom_time = None
_mom_count_today = 0
_mom_date = None

# Gold moves hard outside classic FX sessions too
# Allow momentum any time on weekdays; soft prefer London/NY

def generate_momentum() -> Optional[Dict]:
    global _last_mom_time, _mom_count_today, _mom_date

    today = datetime.now(timezone.utc).date()
    if _mom_date != today:
        _mom_date = today
        _mom_count_today = 0

    if _mom_count_today >= MAX_MOMENTUM_PER_DAY:
        return None

    # Skip pure weekend dead time (Sat full / Sun early UTC)
    wd = datetime.now(timezone.utc).weekday()
    hour = datetime.now(timezone.utc).hour
    if wd == 5:  # Saturday
        return None
    if wd == 6 and hour < 22:  # Sunday before Asia open-ish
        return None

    now = datetime.now(timezone.utc)
    # 15 min cooldown so we can catch sequential waves
    if _last_mom_time and (now - _last_mom_time).total_seconds() < 15 * 60:
        return None

    data = get_multi_timeframe_data()
    h4, m15, m5 = data.get("4h"), data.get("15m"), data.get("5m")
    if m15 is None or m15.empty:
        return None

    tf = m5 if m5 is not None and not m5.empty else m15
    if len(tf) < 6:
        return None

    # --- BIG MOMENTUM: net displacement over last 3–6 bars ---
    def displacement(bars: int):
        chunk = tf.tail(bars)
        net = float(chunk["close"].iloc[-1] - chunk["open"].iloc[0])
        hi = float(chunk["high"].max())
        lo = float(chunk["low"].min())
        return net, hi - lo

    net3, rng3 = displacement(3)
    net5, rng5 = displacement(5)

    # Strong move thresholds for gold (points)
    big_up = net3 >= 6 or net5 >= 10
    big_down = net3 <= -6 or net5 <= -10

    c = tf.iloc[-1]
    body = float(c["close"] - c["open"])
    rng = float(c["high"] - c["low"]) or 1
    engulf = detect_engulfing(tf)
    pin = detect_pin_bar(tf)

    h4_bias = "neutral"
    if h4 is not None and not h4.empty:
        h4_bias = determine_bias(h4)
    m15_bias = determine_bias(m15)

    direction = None

    # Path 1: large displacement (this is what was missing)
    if big_up:
        direction = "BUY"
    elif big_down:
        direction = "SELL"

    # Path 2: candle confirmation aligned with HTF/LTF bias
    if direction is None:
        bias = h4_bias if h4_bias != "neutral" else m15_bias
        if bias == "bullish" and (engulf == "bullish" or pin == "bullish" or (body > 0 and abs(body) / rng > 0.55)):
            direction = "BUY"
        elif bias == "bearish" and (engulf == "bearish" or pin == "bearish" or (body < 0 and abs(body) / rng > 0.55)):
            direction = "SELL"

    # Path 3: 3 of last 4 candles same color + meaningful body sum
    if direction is None and len(tf) >= 4:
        last4 = tf.tail(4)
        ups = sum(1 for _, r in last4.iterrows() if r["close"] > r["open"])
        downs = 4 - ups
        net4 = float(last4["close"].iloc[-1] - last4["open"].iloc[0])
        if ups >= 3 and net4 >= 4:
            direction = "BUY"
        elif downs >= 3 and net4 <= -4:
            direction = "SELL"

    if not direction:
        print(f"Momentum: no trigger net3={net3:.1f} net5={net5:.1f}")
        return None

    price = float(c["close"])

    if direction == "BUY":
        sl = round(float(tf["low"].tail(6).min()) - 4, 2)
        risk = abs(price - sl)
        if risk < 2:
            sl = round(price - 8, 2)
            risk = abs(price - sl)
        if risk > 40:
            sl = round(price - 25, 2)
            risk = abs(price - sl)
        tp1 = round(price + risk * 2.0, 2)
        tp2 = round(price + risk * 1.2, 2)
        el, eh = round(price - 0.6, 2), round(price + 0.5, 2)
    else:
        sl = round(float(tf["high"].tail(6).max()) + 4, 2)
        risk = abs(sl - price)
        if risk < 2:
            sl = round(price + 8, 2)
            risk = abs(sl - price)
        if risk > 40:
            sl = round(price + 25, 2)
            risk = abs(sl - price)
        tp1 = round(price - risk * 2.0, 2)
        tp2 = round(price - risk * 1.2, 2)
        el, eh = round(price - 0.5, 2), round(price + 0.6, 2)

    print(f"Momentum TRIGGER {direction} net3={net3:.1f} net5={net5:.1f} price={price}")

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
        print(f"Momentum posted {_mom_count_today}/{MAX_MOMENTUM_PER_DAY}")
        return True
    return False
