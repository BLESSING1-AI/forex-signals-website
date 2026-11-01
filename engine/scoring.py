"""
Early-entry day-trade scoring — do NOT chase finished moves.
Prefer: HTF bias + pullback to structure + fresh M5/M15 confirmation.
Reject setups where price already ran far from structure (late).
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
        return 5 if (LONDON_START <= h < LONDON_END) or (NY_START <= h < NY_END) else 4
    if (LONDON_START <= h < LONDON_END) or (NY_START <= h < NY_END):
        return 5
    if 6 <= h <= 21:
        return 3
    return 1


def _fresh_bos(df: pd.DataFrame, direction: str) -> bool:
    """BOS only counts if break is on last 1–3 bars (early), not old."""
    if df is None or len(df) < 20:
        return False
    # Compare last close vs swing from bars excluding the very recent impulse
    prior = df.iloc[:-2]
    if len(prior) < 12:
        return False
    from structure import get_recent_swings

    swings = get_recent_swings(prior, n=4)
    price = float(df["close"].iloc[-1])
    prev = float(df["close"].iloc[-3])
    if direction == "bullish":
        highs = [h[1] for h in swings["highs"]]
        if not highs:
            return False
        sh = highs[-1]
        # Just broke or breaking now
        return prev <= sh * 1.0005 and price > sh
    lows = [l[1] for l in swings["lows"]]
    if not lows:
        return False
    sl = lows[-1]
    return prev >= sl * 0.9995 and price < sl


def _is_late_chase(
    price: float,
    structure: float,
    direction: str,
    signed_move: float,
    disp_strong: float,
    risk_proxy: float,
) -> bool:
    """
    True if the move already happened — would be entering late.
    - Distance from structure already large vs planned risk
    - Or 5–8 bar net already near/above strong displacement
    """
    dist = abs(price - structure)
    if risk_proxy > 0 and dist > risk_proxy * 1.35:
        return True
    if abs(signed_move) >= disp_strong * 0.95:
        return True
    return False


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

    # Prefer M5 for early trigger; M15 for structure
    tf = m5 if m5 is not None and not m5.empty and len(m5) >= 10 else m15
    price = float(tf["close"].iloc[-1])

    h4_bias = determine_bias(h4)
    d1_bias = determine_bias(d1) if d1 is not None and not d1.empty else "neutral"
    h1_bias = determine_bias(h1) if h1 is not None and not h1.empty else "neutral"
    m15_bias = determine_bias(m15)

    # HTF direction first — day trades need a side
    if h4_bias in ("bullish", "bearish"):
        direction = h4_bias
    elif h1_bias in ("bullish", "bearish"):
        direction = h1_bias
    elif m15_bias in ("bullish", "bearish"):
        direction = m15_bias
    else:
        net5, _ = displacement_metrics(tf, 5)
        if abs(net5) < disp_ok * 0.5:
            return None
        direction = "bullish" if net5 > 0 else "bearish"

    dir_label = "BUY" if direction == "bullish" else "SELL"

    # Structure level for SL / proximity
    structure = find_nearby_structure_level(m15, direction)
    if structure is None:
        structure = (
            float(m15["low"].tail(25).min())
            if direction == "bullish"
            else float(m15["high"].tail(25).max())
        )

    net2, rng2 = displacement_metrics(tf, 2)
    net3, rng3 = displacement_metrics(tf, 3)
    net5, rng5 = displacement_metrics(tf, 5)
    net8, _ = displacement_metrics(tf, 8)
    signed5 = net5 if direction == "bullish" else -net5
    signed2 = net2 if direction == "bullish" else -net2
    signed3 = net3 if direction == "bullish" else -net3

    # Planned risk proxy for late-chase check
    risk_proxy = abs(price - structure) + sl_buffer
    if risk_proxy < risk_min:
        risk_proxy = risk_min

    # HARD: reject chasing a move that already ran
    if _is_late_chase(price, structure, direction, signed5, disp_strong, risk_proxy):
        # Allow only if LAST 2 bars are a pullback toward structure (not extension)
        pullback_now = (
            (direction == "bullish" and float(tf["close"].iloc[-1]) < float(tf["close"].iloc[-3]))
            or (direction == "bearish" and float(tf["close"].iloc[-1]) > float(tf["close"].iloc[-3]))
        )
        near_struct = abs(price - structure) <= risk_proxy * 0.55
        if not (pullback_now and near_struct):
            print(f"{symbol}: LATE CHASE skipped (move already happened)")
            return None

    # Confirmations — prefer FRESH
    fresh_bos = _fresh_bos(tf, direction) or _fresh_bos(m15, direction)
    bos = detect_bos(tf)
    choch = detect_choch(m15)
    sweep = detect_liquidity_sweep(tf) or detect_liquidity_sweep(m15)
    fvg = detect_fvg(tf) or detect_fvg(m15)
    engulf = detect_engulfing(tf) or detect_engulfing(m15)
    pin = detect_pin_bar(tf) or detect_pin_bar(m15)

    # Near structure? (early / pullback entry)
    near = abs(price - structure) <= max(sl_buffer * 2.2, risk_proxy * 0.5)

    reasons: List[str] = []
    score = 0

    # --- Structure / trigger (max 24) ---
    struct_pts = 0
    if fresh_bos:
        struct_pts += 14
        reasons.append("Fresh BOS")
    elif bos == direction:
        struct_pts += 6  # old BOS worth less (can be late)
        reasons.append("BOS")
    if choch == direction:
        struct_pts += 10
        reasons.append("CHoCH")
    if engulf == direction:
        struct_pts += 10
        reasons.append("Engulf")
    if pin == direction:
        struct_pts += 9
        reasons.append("Pin")
    if near:
        struct_pts += 6
        reasons.append("At structure")
    if sweep == direction:
        struct_pts += 8
        reasons.append("Sweep")
    struct_pts = min(24, struct_pts)
    score += struct_pts

    # --- Early momentum (max 18): reward START of move, not finished run ---
    mom_pts = 0
    if 0 < signed2 <= disp_solid and signed5 < disp_strong * 0.85:
        # Fresh impulse starting
        mom_pts = 16
        reasons.append("Early impulse")
    elif 0 < signed3 <= disp_solid * 1.1 and signed5 < disp_strong:
        mom_pts = 12
        reasons.append("Building momentum")
    elif signed5 >= disp_ok and signed5 < disp_strong * 0.7:
        mom_pts = 8
        reasons.append("Ongoing move")
    elif signed5 >= disp_strong * 0.7:
        mom_pts = 2  # almost done — weak points
        reasons.append("Extended")
    elif near and (engulf == direction or pin == direction):
        mom_pts = 10
        reasons.append("Rejection at level")
    score += mom_pts

    # --- HTF (max 18) ---
    htf_pts = 0
    if h4_bias == direction and h1_bias == direction:
        htf_pts = 18
        reasons.append("H4+H1")
    elif h4_bias == direction:
        htf_pts = 14
        reasons.append("H4 bias")
    elif h1_bias == direction:
        htf_pts = 11
        reasons.append("H1 bias")
    elif d1_bias == direction:
        htf_pts = 8
        reasons.append("D1 bias")
    elif h4_bias != "neutral" and h4_bias != direction:
        htf_pts = 0
        reasons.append("HTF oppose")
    else:
        htf_pts = 4
    score += htf_pts

    # Must have HTF or strong structure for day trade
    if htf_pts < 8 and struct_pts < 14:
        return None

    # FVG (max 10)
    fvg_pts = 0
    fvg_ok = False
    if fvg and fvg["direction"] == direction:
        fvg_pts = 10
        fvg_ok = True
        reasons.append("FVG")
    score += fvg_pts

    # Vol mild (max 8) — expansion OK early, not required
    vol_pts = 0
    avg_rng = float((m15["high"] - m15["low"]).tail(20).mean()) or 1
    if rng3 >= avg_rng * 1.2 or rng3 >= vol_abs_mid * 0.5:
        vol_pts = 6
    elif rng2 > 0:
        vol_pts = 3
    score += vol_pts

    sess = _session_points(session_mode)
    score += sess

    # Entry zone: prefer structure-based, not chasing price
    tick = max(price * 0.00005, 0.5) if symbol == "BTCUSD" else 0.5
    if direction == "bullish":
        # Limit-style zone near structure / slight above
        el = round(min(structure, price) - tick, decimals)
        eh = round(min(price + tick * 2, structure + sl_buffer * 0.8), decimals)
        if el > eh:
            el, eh = round(price - tick * 2, decimals), round(price + tick, decimals)
        stop = round(min(structure, el) - sl_buffer, decimals)
        if stop >= el:
            stop = round(el - sl_buffer, decimals)
    else:
        el = round(max(price - tick * 2, structure - sl_buffer * 0.8), decimals)
        eh = round(max(structure, price) + tick, decimals)
        if el > eh:
            el, eh = round(price - tick, decimals), round(price + tick * 2, decimals)
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

    rr = round(abs(tp1 - mid) / risk, 2) if risk else 0.0
    rr_pts = 8 if rr >= 2.0 else (6 if rr + 0.05 >= MIN_RR else 0)
    if rr + 1e-9 < MIN_RR:
        return None
    score += rr_pts

    nb = max(0, min(int(news_bonus), NEWS_SCORE_BONUS_MAX))
    score += nb
    score = int(max(0, min(100, score)))

    # Need a real trigger, not just bias
    if struct_pts < 8 and mom_pts < 8:
        return None

    if score >= A_PLUS_SCORE:
        tier, action = "A+", "signal"
    elif score >= MIN_SIGNAL_SCORE:
        tier, action = "A", "signal"
    elif score >= WATCHLIST_SCORE:
        tier, action = "WATCHLIST", "watchlist"
    else:
        return None

    # If only extended momentum without near structure → watchlist max
    if "Extended" in reasons and not near and action == "signal":
        tier, action = "WATCHLIST", "watchlist"
        reasons.append("Wait pullback")

    model = "pullback" if near else "continuation"
    if fresh_bos:
        model = "fresh_bos"
    if sweep == direction:
        model = "sweep_reversal"
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
            "bos": bos if bos == direction else None,
            "fresh_bos": fresh_bos,
            "choch": choch,
            "sweep": sweep,
            "fvg": fvg_ok,
            "engulf": engulf,
            "pin": pin,
            "near_structure": near,
        },
    }
