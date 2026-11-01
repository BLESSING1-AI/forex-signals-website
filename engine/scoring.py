"""
Day-trade + momentum scoring 0–100 — XAU / BTC.
Multiple valid confirmation paths (not all-must-pass).
TP1 closest (~1.6–1.8R), TP3 furthest (~5R).
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
        if (LONDON_START <= h < LONDON_END) or (NY_START <= h < NY_END):
            return 5
        return 4  # crypto always tradable
    # Gold: peak during London / NY
    if (LONDON_START <= h < LONDON_END) or (NY_START <= h < NY_END):
        return 5
    if 6 <= h <= 21:
        return 3
    return 1


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
    disp_vote = float(meta["disp_vote"])
    risk_min = float(meta["risk_min"])
    risk_max = float(meta["risk_max"])
    vol_abs_strong = float(meta["vol_abs_strong"])
    vol_abs_mid = float(meta["vol_abs_mid"])
    decimals = int(meta.get("decimals", 2))
    session_mode = meta.get("session_mode", "fx")

    if m15 is None or m15.empty or h4 is None or h4.empty:
        return None

    tf = m5 if m5 is not None and not m5.empty and len(m5) >= 8 else m15
    price = float(tf["close"].iloc[-1])

    h4_bias = determine_bias(h4)
    d1_bias = determine_bias(d1) if d1 is not None and not d1.empty else "neutral"
    h1_bias = determine_bias(h1) if h1 is not None and not h1.empty else "neutral"
    m15_bias = determine_bias(m15)

    bos = detect_bos(tf)
    choch = detect_choch(m15)
    sweep = detect_liquidity_sweep(tf)
    fvg = detect_fvg(tf)
    engulf = detect_engulfing(tf)
    pin = detect_pin_bar(tf)
    # Also check M15 candle patterns (not only M5)
    engulf_m15 = detect_engulfing(m15)
    pin_m15 = detect_pin_bar(m15)
    if not engulf:
        engulf = engulf_m15
    if not pin:
        pin = pin_m15

    net3, rng3 = displacement_metrics(tf, 3)
    net5, rng5 = displacement_metrics(tf, 5)
    net8, rng8 = displacement_metrics(tf, 8)
    net15, _ = displacement_metrics(m15, 6)

    # --- Direction by weighted votes (multiple valid paths) ---
    votes = {"bullish": 0, "bearish": 0}
    for sig, w in [
        (bos, 3),
        (choch, 3),
        (sweep, 2),
        (engulf, 2),
        (pin, 2),
        (h4_bias if h4_bias != "neutral" else None, 3),
        (h1_bias if h1_bias != "neutral" else None, 2),
        (m15_bias if m15_bias != "neutral" else None, 1),
    ]:
        if sig in ("bullish", "bearish"):
            votes[sig] += w
    if net5 >= disp_vote:
        votes["bullish"] += 2
    if net5 <= -disp_vote:
        votes["bearish"] += 2
    if abs(net15) >= disp_ok:
        votes["bullish" if net15 > 0 else "bearish"] += 2
    if fvg and fvg["direction"] in votes:
        votes[fvg["direction"]] += 1

    if votes["bullish"] == votes["bearish"]:
        # Fall back to short net displacement
        if abs(net5) < disp_ok * 0.5 and abs(net15) < disp_ok * 0.5:
            return None
        direction = "bullish" if (net5 + net15) > 0 else "bearish"
    else:
        direction = "bullish" if votes["bullish"] > votes["bearish"] else "bearish"

    dir_label = "BUY" if direction == "bullish" else "SELL"
    reasons: List[str] = []
    score = 0

    # Structure path (max 22)
    struct_pts = 0
    if bos == direction:
        struct_pts += 12
        reasons.append("BOS")
    if choch == direction:
        struct_pts += 10
        reasons.append("CHoCH")
    if engulf == direction or pin == direction:
        struct_pts += 8
        reasons.append(f"{engulf or pin}")
    if m15_bias == direction:
        struct_pts += 4
    signed_pre = net5 if direction == "bullish" else -net5
    # Impulse can fill structure gap
    if struct_pts < 10 and signed_pre >= disp_ok:
        struct_pts = max(struct_pts, 10)
        if "Impulse" not in reasons:
            reasons.append("Impulse")
    # Pullback day-trade path: HTF aligned + rejection only
    if struct_pts < 8 and (engulf == direction or pin == direction) and (
        h4_bias == direction or h1_bias == direction
    ):
        struct_pts = max(struct_pts, 12)
        if "Pullback rejection" not in reasons:
            reasons.append("Pullback rejection")
    struct_pts = min(22, struct_pts)
    score += struct_pts

    # Momentum (max 20)
    mom_pts = 0
    signed = net5 if direction == "bullish" else -net5
    signed15 = net15 if direction == "bullish" else -net15
    if signed >= disp_strong or abs(net8) >= disp_strong * 1.1:
        mom_pts = 20
        reasons.append("Strong displacement")
    elif signed >= disp_solid or signed15 >= disp_solid:
        mom_pts = 15
        reasons.append("Solid momentum")
    elif signed >= disp_ok or signed15 >= disp_ok:
        mom_pts = 10
        reasons.append("Directional move")
    elif signed >= disp_ok * 0.4 or signed15 >= disp_ok * 0.4:
        mom_pts = 6
    score += mom_pts

    # HTF (max 18) — H1 counts for day trades
    htf_pts = 0
    if h4_bias == direction and d1_bias == direction:
        htf_pts = 18
        reasons.append("D1+H4")
    elif h4_bias == direction and h1_bias == direction:
        htf_pts = 16
        reasons.append("H4+H1")
    elif h4_bias == direction:
        htf_pts = 12
        reasons.append("H4 bias")
    elif h1_bias == direction:
        htf_pts = 10
        reasons.append("H1 bias")
    elif d1_bias == direction:
        htf_pts = 8
        reasons.append("D1 bias")
    elif h4_bias != "neutral" and h4_bias != direction:
        htf_pts = 2  # mild penalty, not zero
        reasons.append("HTF soft oppose")
    else:
        htf_pts = 6 if mom_pts >= 10 else 3
    score += htf_pts

    # Liquidity (max 10)
    liq_pts = 0
    if sweep == direction:
        liq_pts = 10
        reasons.append("Sweep")
    elif sweep is not None:
        liq_pts = 3
    score += liq_pts

    # FVG (max 10)
    fvg_pts = 0
    fvg_ok = False
    if fvg and fvg["direction"] == direction:
        fvg_pts = 10
        fvg_ok = True
        reasons.append("FVG")
    elif fvg:
        fvg_pts = 2
    score += fvg_pts

    # Volatility (max 10)
    vol_pts = 0
    avg_rng = float((m15["high"] - m15["low"]).tail(20).mean()) or 1
    if rng5 >= avg_rng * 1.8 or rng5 >= vol_abs_strong:
        vol_pts = 10
        reasons.append("Expansion")
    elif rng5 >= avg_rng * 1.2 or rng5 >= vol_abs_mid:
        vol_pts = 7
    elif rng5 >= avg_rng * 0.7 or rng5 >= vol_abs_mid * 0.35:
        vol_pts = 4
    score += vol_pts

    sess = _session_points(session_mode)
    score += sess
    if sess >= 5:
        reasons.append("Session")

    # Levels
    structure = find_nearby_structure_level(m15, direction)
    if structure is None:
        structure = (
            float(m15["low"].tail(20).min())
            if direction == "bullish"
            else float(m15["high"].tail(20).max())
        )

    tick = max(price * 0.00005, 0.5) if symbol == "BTCUSD" else 0.5
    if direction == "bullish":
        el = round(min(structure + tick, price - tick * 2), decimals)
        eh = round(price + tick, decimals)
        if el > eh:
            el, eh = round(price - tick * 3, decimals), round(price + tick, decimals)
        stop = round(min(structure, el) - sl_buffer, decimals)
        if stop >= el:
            stop = round(el - sl_buffer, decimals)
    else:
        el = round(price - tick, decimals)
        eh = round(max(structure - tick, price + tick * 2), decimals)
        if el > eh:
            el, eh = round(price - tick, decimals), round(price + tick * 3, decimals)
        stop = round(max(structure, eh) + sl_buffer, decimals)
        if stop <= eh:
            stop = round(eh + sl_buffer, decimals)

    mid = (el + eh) / 2.0
    risk = abs(mid - stop)
    if risk < risk_min:
        # Widen SL slightly instead of killing setup
        if direction == "bullish":
            stop = round(mid - risk_min, decimals)
        else:
            stop = round(mid + risk_min, decimals)
        risk = abs(mid - stop)
    if risk > risk_max:
        stop = (
            round(mid - risk_max * 0.45, decimals)
            if direction == "bullish"
            else round(mid + risk_max * 0.45, decimals)
        )
        risk = abs(mid - stop)

    r1 = max(MIN_RR, 1.6)
    if direction == "bullish":
        tp1 = round(mid + risk * r1, decimals)
        tp2 = round(mid + risk * 3.0, decimals)
        tp3 = round(mid + risk * 5.0, decimals)
    else:
        tp1 = round(mid - risk * r1, decimals)
        tp2 = round(mid - risk * 3.0, decimals)
        tp3 = round(mid - risk * 5.0, decimals)

    rr = abs(tp1 - mid) / risk if risk else 0.0
    rr = round(rr, 2)

    rr_pts = 0
    if rr >= 2.5:
        rr_pts = 10
    elif rr >= 2.0:
        rr_pts = 8
    elif rr + 0.05 >= MIN_RR:
        rr_pts = 6
        rr = max(rr, MIN_RR)
    score += rr_pts

    nb = max(0, min(int(news_bonus), NEWS_SCORE_BONUS_MAX))
    score += nb
    if nb:
        reasons.append(f"News +{nb}")

    score = int(max(0, min(100, score)))

    if rr + 1e-9 < MIN_RR:
        return None
    # Soft floor — need either structure OR momentum
    if mom_pts < 4 and struct_pts < 6:
        return None

    if score >= A_PLUS_SCORE:
        tier, action = "A+", "signal"
    elif score >= MIN_SIGNAL_SCORE:
        tier, action = "A", "signal"
    elif score >= WATCHLIST_SCORE:
        tier, action = "WATCHLIST", "watchlist"
    else:
        return None

    model = "day_trade"
    if sweep and (choch or bos):
        model = "liquidity_reversal"
    elif fvg_ok and mom_pts >= 8:
        model = "pullback"
    elif mom_pts >= 15 and (bos or signed >= disp_solid):
        model = "breakout"
    elif h4_bias == direction or h1_bias == direction:
        model = "trend_continuation"

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
            "choch": choch,
            "sweep": sweep,
            "fvg": fvg_ok,
            "engulf": engulf,
            "pin": pin,
        },
    }
