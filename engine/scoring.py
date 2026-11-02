"""
Day-trade + momentum breakout scoring.
Two valid paths:
  1) Pullback to structure + rejection
  2) Momentum breakout (fresh strong displacement + HTF align) — catch the move
Only skip if move is extreme AND already exhausted (last bars reversing).
"""
from typing import Dict, Any, Optional, List
import pandas as pd
from datetime import datetime, timezone

from structure import (
    determine_bias,
    detect_engulfing,
    detect_pin_bar,
    detect_bos,
    detect_choch,
    detect_liquidity_sweep,
    detect_fvg,
    displacement_metrics,
    find_nearby_structure_level,
    get_recent_swings,
)
from config import (
    SYMBOLS,
    MIN_SIGNAL_SCORE,
    WATCHLIST_SCORE,
    A_PLUS_SCORE,
    MIN_RR,
    LONDON_START,
    LONDON_END,
    NY_START,
    NY_END,
    NEWS_SCORE_BONUS_MAX,
)


def _session_points(mode: str) -> int:
    h = datetime.now(timezone.utc).hour
    if mode == "crypto":
        return 5
    if LONDON_START <= h < NY_END:
        return 5
    return 2


def _fresh_break(df: pd.DataFrame, direction: str) -> bool:
    if df is None or len(df) < 20:
        return False
    prior = df.iloc[:-1]
    swings = get_recent_swings(prior, n=5)
    price = float(df["close"].iloc[-1])
    hi = float(df["high"].iloc[-1])
    lo = float(df["low"].iloc[-1])
    if direction == "bullish":
        highs = [h[1] for h in swings["highs"]]
        if not highs:
            return False
        sh = max(highs[-2:]) if len(highs) >= 2 else highs[-1]
        return hi > sh and price > sh * 0.999
    lows = [l[1] for l in swings["lows"]]
    if not lows:
        return False
    sl = min(lows[-2:]) if len(lows) >= 2 else lows[-1]
    return lo < sl and price < sl * 1.001


def score_setup(
    d1: pd.DataFrame,
    h4: pd.DataFrame,
    m15: pd.DataFrame,
    m5: Optional[pd.DataFrame] = None,
    news_bonus: int = 0,
    symbol: str = "XAUUSD",
    h1: Optional[pd.DataFrame] = None,
) -> Optional[Dict[str, Any]]:
    meta = SYMBOLS.get(symbol) or SYMBOLS["XAUUSD"]
    sl_buffer = float(meta["sl_buffer"])
    disp_strong = float(meta["disp_strong"])
    disp_solid = float(meta["disp_solid"])
    disp_ok = float(meta["disp_ok"])
    risk_min = float(meta["risk_min"])
    risk_max = float(meta["risk_max"])
    vol_abs_mid = float(meta["vol_abs_mid"])
    decimals = int(meta.get("decimals", 2))
    session_mode = meta.get("session_mode", "fx")

    if m15 is None or m15.empty or h4 is None or h4.empty:
        return None

    tf = m5 if m5 is not None and not m5.empty and len(m5) >= 10 else m15
    price = float(tf["close"].iloc[-1])

    h4_bias = determine_bias(h4)
    d1_bias = determine_bias(d1) if d1 is not None and not d1.empty else "neutral"
    h1_bias = determine_bias(h1) if h1 is not None and not h1.empty else "neutral"
    m15_bias = determine_bias(m15)

    net2, rng2 = displacement_metrics(tf, 2)
    net3, rng3 = displacement_metrics(tf, 3)
    net5, rng5 = displacement_metrics(tf, 5)
    net8, _ = displacement_metrics(tf, 8)
    net_m15, _ = displacement_metrics(m15, 4)

    # Direction: prefer HTF, else short-term displacement
    if h4_bias in ("bullish", "bearish"):
        direction = h4_bias
    elif h1_bias in ("bullish", "bearish"):
        direction = h1_bias
    elif abs(net3) >= disp_ok * 0.8:
        direction = "bullish" if net3 > 0 else "bearish"
    elif m15_bias in ("bullish", "bearish"):
        direction = m15_bias
    elif abs(net5) >= disp_ok * 0.5:
        direction = "bullish" if net5 > 0 else "bearish"
    else:
        return None

    dir_label = "BUY" if direction == "bullish" else "SELL"
    signed2 = net2 if direction == "bullish" else -net2
    signed3 = net3 if direction == "bullish" else -net3
    signed5 = net5 if direction == "bullish" else -net5
    signed8 = net8 if direction == "bullish" else -net8
    signed_m15 = net_m15 if direction == "bullish" else -net_m15

    structure = find_nearby_structure_level(m15, direction)
    if structure is None:
        structure = (
            float(m15["low"].tail(25).min())
            if direction == "bullish"
            else float(m15["high"].tail(25).max())
        )

    # Exhaustion only: huge move AND last candle opposite (buying the top)
    last_body = float(tf["close"].iloc[-1] - tf["open"].iloc[-1])
    last_against = (direction == "bullish" and last_body < 0) or (
        direction == "bearish" and last_body > 0
    )
    exhausted = signed5 >= disp_strong * 1.4 and last_against
    if exhausted:
        print(f"{symbol}: exhausted spike — skip")
        return None

    fresh = _fresh_break(tf, direction) or _fresh_break(m15, direction)
    bos = detect_bos(tf)
    choch = detect_choch(m15)
    sweep = detect_liquidity_sweep(tf) or detect_liquidity_sweep(m15)
    fvg = detect_fvg(tf) or detect_fvg(m15)
    engulf = detect_engulfing(tf) or detect_engulfing(m15)
    pin = detect_pin_bar(tf) or detect_pin_bar(m15)

    near = abs(price - structure) <= max(sl_buffer * 2.5, abs(price - structure) * 0 + sl_buffer * 2.5)
    # recompute near properly
    near = abs(price - structure) <= sl_buffer * 2.8

    # Momentum breakout active?
    breakout = (
        (signed2 >= disp_ok or signed3 >= disp_solid * 0.7)
        and signed5 < disp_strong * 1.6  # not absurdly done
        and (fresh or bos == direction or signed3 >= disp_solid)
    )

    reasons: List[str] = []
    score = 0

    # Structure (max 22)
    struct_pts = 0
    if fresh:
        struct_pts += 14
        reasons.append("Fresh break")
    elif bos == direction:
        struct_pts += 10
        reasons.append("BOS")
    if choch == direction:
        struct_pts += 8
        reasons.append("CHoCH")
    if engulf == direction:
        struct_pts += 9
        reasons.append("Engulf")
    if pin == direction:
        struct_pts += 8
        reasons.append("Pin")
    if near:
        struct_pts += 6
        reasons.append("At structure")
    if sweep == direction:
        struct_pts += 8
        reasons.append("Sweep")
    struct_pts = min(22, struct_pts)
    score += struct_pts

    # Momentum (max 22) — reward real strength
    mom_pts = 0
    if breakout and signed3 >= disp_solid:
        mom_pts = 22
        reasons.append("Momentum breakout")
    elif breakout:
        mom_pts = 18
        reasons.append("Breakout forming")
    elif signed2 >= disp_ok and signed5 < disp_strong * 1.2:
        mom_pts = 16
        reasons.append("Early impulse")
    elif signed5 >= disp_ok or signed_m15 >= disp_ok:
        mom_pts = 12
        reasons.append("Directional")
    elif near and (engulf == direction or pin == direction):
        mom_pts = 12
        reasons.append("Rejection")
    elif signed5 > 0:
        mom_pts = 6
    score += mom_pts

    # HTF (max 18)
    htf_pts = 0
    if h4_bias == direction and h1_bias == direction:
        htf_pts = 18
        reasons.append("H4+H1")
    elif h4_bias == direction:
        htf_pts = 14
        reasons.append("H4")
    elif h1_bias == direction:
        htf_pts = 12
        reasons.append("H1")
    elif d1_bias == direction:
        htf_pts = 8
        reasons.append("D1")
    elif h4_bias != "neutral" and h4_bias != direction:
        # Counter-trend breakout needs stronger mom
        if mom_pts >= 18:
            htf_pts = 4
            reasons.append("Counter HTF")
        else:
            htf_pts = 0
            reasons.append("HTF oppose")
    else:
        htf_pts = 5
    score += htf_pts

    if htf_pts == 0 and mom_pts < 18:
        return None

    fvg_pts = 0
    fvg_ok = bool(fvg and fvg["direction"] == direction)
    if fvg_ok:
        fvg_pts = 8
        reasons.append("FVG")
    score += fvg_pts

    vol_pts = 0
    avg_rng = float((m15["high"] - m15["low"]).tail(20).mean()) or 1
    if rng3 >= avg_rng * 1.1 or rng3 >= vol_abs_mid * 0.45:
        vol_pts = 6
    elif rng2 > 0:
        vol_pts = 3
    score += vol_pts

    sess = _session_points(session_mode)
    score += sess

    # Need some trigger
    if mom_pts < 6 and struct_pts < 8:
        return None

    # Levels — for breakout use tighter structure from recent swing
    tick = max(price * 0.00005, 0.5) if symbol == "BTCUSD" else 0.5
    if direction == "bullish":
        if breakout and not near:
            el = round(price - tick * 3, decimals)
            eh = round(price + tick * 2, decimals)
            stop = round(min(float(tf["low"].tail(5).min()), el) - sl_buffer * 0.7, decimals)
        else:
            el = round(min(structure, price) - tick, decimals)
            eh = round(price + tick * 2, decimals)
            stop = round(min(structure, el) - sl_buffer, decimals)
        if stop >= el:
            stop = round(el - sl_buffer, decimals)
    else:
        if breakout and not near:
            el = round(price - tick * 2, decimals)
            eh = round(price + tick * 3, decimals)
            stop = round(max(float(tf["high"].tail(5).max()), eh) + sl_buffer * 0.7, decimals)
        else:
            el = round(price - tick * 2, decimals)
            eh = round(max(structure, price) + tick, decimals)
            stop = round(max(structure, eh) + sl_buffer, decimals)
        if stop <= eh:
            stop = round(eh + sl_buffer, decimals)

    mid = (el + eh) / 2.0
    risk = abs(mid - stop)
    if risk < risk_min:
        stop = round(mid - risk_min, decimals) if direction == "bullish" else round(mid + risk_min, decimals)
        risk = abs(mid - stop)
    if risk > risk_max:
        stop = (
            round(mid - risk_max * 0.4, decimals)
            if direction == "bullish"
            else round(mid + risk_max * 0.4, decimals)
        )
        risk = abs(mid - stop)

    r1 = max(MIN_RR, 1.5)
    if direction == "bullish":
        tp1 = round(mid + risk * r1, decimals)
        tp2 = round(mid + risk * 2.8, decimals)
        tp3 = round(mid + risk * 4.5, decimals)
    else:
        tp1 = round(mid - risk * r1, decimals)
        tp2 = round(mid - risk * 2.8, decimals)
        tp3 = round(mid - risk * 4.5, decimals)

    rr = round(abs(tp1 - mid) / risk, 2) if risk else 0.0
    if rr + 1e-9 < MIN_RR:
        return None
    score += 6 if rr >= 1.5 else 0

    nb = max(0, min(int(news_bonus), NEWS_SCORE_BONUS_MAX))
    score += nb
    score = int(max(0, min(100, score)))

    if score >= A_PLUS_SCORE:
        tier, action = "A+", "signal"
    elif score >= MIN_SIGNAL_SCORE:
        tier, action = "A", "signal"
    elif score >= WATCHLIST_SCORE:
        tier, action = "WATCHLIST", "watchlist"
    else:
        return None

    model = "momentum_breakout" if breakout else ("pullback" if near else "continuation")
    if sweep == direction:
        model = "sweep"
    if fvg_ok and near:
        model = "fvg_pullback"

    return {
        "pair": symbol,
        "direction": dir_label,
        "bias": direction,
        "score": score,
        "tier": tier,
        "action": action,
        "model": model,
        "reasons": reasons,
        "entry_zone": f"{el}-{eh}",
        "stop_loss": str(stop),
        "tp1": str(tp1),
        "tp2": str(tp2),
        "tp3": str(tp3),
        "rr": rr,
        "structure_level": round(float(structure), decimals),
        "htf": h4_bias,
        "h1": h1_bias,
        "momentum_pts": mom_pts,
        "struct_pts": struct_pts,
        "confirmations": {
            "bos": bos,
            "fresh": fresh,
            "breakout": breakout,
            "sweep": sweep,
            "fvg": fvg_ok,
            "engulf": engulf,
            "pin": pin,
            "near": near,
        },
    }
