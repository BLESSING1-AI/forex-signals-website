"""
Weighted setup quality score 0–100.
Flexible combinations — not all confirmations required.
"""
from typing import Dict, Any, Optional, List, Tuple
import pandas as pd

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
    MIN_SIGNAL_SCORE,
    WATCHLIST_SCORE,
    A_PLUS_SCORE,
    MIN_RR,
    XAU_SL_BUFFER,
    LONDON_START,
    LONDON_END,
    NY_START,
    NY_END,
    NEWS_SCORE_BONUS_MAX,
)
from datetime import datetime, timezone


def _session_points() -> int:
    h = datetime.now(timezone.utc).hour
    if (LONDON_START <= h < LONDON_END) or (NY_START <= h < NY_END):
        return 5
    if 6 <= h <= 21:
        return 2
    return 0


def score_setup(
    d1: pd.DataFrame,
    h4: pd.DataFrame,
    m15: pd.DataFrame,
    m5: Optional[pd.DataFrame] = None,
    news_bonus: int = 0,
) -> Optional[Dict[str, Any]]:
    """
    Returns scored setup dict or None if no directional lean at all.
    Weights (100):
      Structure 20 | Momentum 20 | HTF 15 | Liquidity 10 |
      FVG/zone 10 | Vol 10 | Session 5 | RR 10
    """
    if m15 is None or m15.empty or h4 is None or h4.empty:
        return None

    tf = m5 if m5 is not None and not m5.empty and len(m5) >= 8 else m15
    price = float(tf["close"].iloc[-1])

    h4_bias = determine_bias(h4)
    d1_bias = determine_bias(d1) if d1 is not None and not d1.empty else "neutral"
    m15_bias = determine_bias(m15)

    bos = detect_bos(tf)
    choch = detect_choch(m15)
    sweep = detect_liquidity_sweep(tf)
    fvg = detect_fvg(tf)
    engulf = detect_engulfing(tf)
    pin = detect_pin_bar(tf)
    net3, rng3 = displacement_metrics(tf, 3)
    net5, rng5 = displacement_metrics(tf, 5)
    net8, rng8 = displacement_metrics(tf, 8)

    # Infer direction from strongest cues (not all required)
    votes = {"bullish": 0, "bearish": 0}
    for sig, w in [
        (bos, 3),
        (choch, 3),
        (sweep, 2),
        (engulf, 2),
        (pin, 2),
        (h4_bias if h4_bias != "neutral" else None, 2),
        (m15_bias if m15_bias != "neutral" else None, 1),
    ]:
        if sig in ("bullish", "bearish"):
            votes[sig] += w
    if net5 >= 8:
        votes["bullish"] += 2
    if net5 <= -8:
        votes["bearish"] += 2
    if fvg and fvg["direction"] in votes:
        votes[fvg["direction"]] += 1

    if votes["bullish"] == votes["bearish"]:
        if abs(net5) < 5:
            return None
        direction = "bullish" if net5 > 0 else "bearish"
    else:
        direction = "bullish" if votes["bullish"] > votes["bearish"] else "bearish"

    dir_label = "BUY" if direction == "bullish" else "SELL"
    reasons: List[str] = []
    score = 0

    # --- Structure 20 ---
    struct_pts = 0
    if bos == direction:
        struct_pts += 12
        reasons.append("BOS confirmed")
    if choch == direction:
        struct_pts += 10
        reasons.append("CHoCH")
    if engulf == direction or pin == direction:
        struct_pts += 6
        reasons.append(f"{engulf or pin} rejection")
    if m15_bias == direction:
        struct_pts += 4
    struct_pts = min(20, struct_pts)
    score += struct_pts

    # --- Momentum / displacement 20 ---
    mom_pts = 0
    signed = net5 if direction == "bullish" else -net5
    if signed >= 22 or abs(net8) >= 30:
        mom_pts = 20
        reasons.append("Strong displacement")
    elif signed >= 12:
        mom_pts = 15
        reasons.append("Solid momentum")
    elif signed >= 6:
        mom_pts = 10
        reasons.append("Directional momentum")
    elif signed >= 3:
        mom_pts = 5
    score += mom_pts

    # --- HTF bias 15 (strong bonus, not hard reject) ---
    htf_pts = 0
    if h4_bias == direction and d1_bias == direction:
        htf_pts = 15
        reasons.append("D1+H4 alignment")
    elif h4_bias == direction:
        htf_pts = 12
        reasons.append("H4 alignment")
    elif d1_bias == direction:
        htf_pts = 8
        reasons.append("D1 alignment")
    elif h4_bias != "neutral" and h4_bias != direction:
        # opposing HTF — reduce but do not zero entire setup
        htf_pts = 0
        reasons.append("HTF opposing (score reduced)")
    else:
        htf_pts = 3
    score += htf_pts

    # --- Liquidity / sweep 10 ---
    liq_pts = 0
    if sweep == direction:
        liq_pts = 10
        reasons.append("Liquidity sweep")
    elif sweep is not None:
        liq_pts = 2
    score += liq_pts

    # --- FVG / entry zone 10 ---
    fvg_pts = 0
    fvg_ok = False
    if fvg and fvg["direction"] == direction:
        fvg_pts = 10
        fvg_ok = True
        reasons.append("FVG valid")
    elif fvg:
        fvg_pts = 2
    score += fvg_pts

    # --- Volume/volatility proxy 10 (range expansion) ---
    vol_pts = 0
    avg_rng = float((m15["high"] - m15["low"]).tail(20).mean()) or 1
    if rng5 >= avg_rng * 2.2:
        vol_pts = 10
        reasons.append("Range expansion")
    elif rng5 >= avg_rng * 1.4:
        vol_pts = 6
    elif rng5 >= avg_rng:
        vol_pts = 3
    score += vol_pts

    # --- Session 5 ---
    sess = _session_points()
    score += sess
    if sess >= 5:
        reasons.append("London/NY session")

    # Build levels for RR
    structure = find_nearby_structure_level(m15, direction)
    if structure is None:
        structure = (
            float(m15["low"].tail(25).min())
            if direction == "bullish"
            else float(m15["high"].tail(25).max())
        )

    if direction == "bullish":
        el = round(min(structure + 1, price - 1.2), 2)
        eh = round(price + 0.6, 2)
        if el > eh:
            el, eh = round(price - 2, 2), round(price + 0.5, 2)
        stop = round(min(structure, el) - XAU_SL_BUFFER, 2)
        if stop >= el:
            stop = round(el - XAU_SL_BUFFER, 2)
    else:
        el = round(price - 0.6, 2)
        eh = round(max(structure - 1, price + 1.2), 2)
        if el > eh:
            el, eh = round(price - 0.5, 2), round(price + 2, 2)
        stop = round(max(structure, eh) + XAU_SL_BUFFER, 2)
        if stop <= eh:
            stop = round(eh + XAU_SL_BUFFER, 2)

    mid = (el + eh) / 2
    risk = abs(mid - stop)
    if risk < 6:
        return None
    if risk > 90:
        stop = round(mid - 40, 2) if direction == "bullish" else round(mid + 40, 2)
        risk = abs(mid - stop)

    # TP order: TP1 furthest (5R), TP2 3R, TP3 closest 1.5R — user preference
    # For RR check use closest TP at 1.8R minimum path
    tp_close = round(mid + risk * MIN_RR, 2) if direction == "bullish" else round(mid - risk * MIN_RR, 2)
    tp1 = round(mid + risk * 5.0, 2) if direction == "bullish" else round(mid - risk * 5.0, 2)
    tp2 = round(mid + risk * 3.0, 2) if direction == "bullish" else round(mid - risk * 3.0, 2)
    tp3 = round(mid + risk * 1.8, 2) if direction == "bullish" else round(mid - risk * 1.8, 2)

    rr = abs(tp3 - mid) / risk if risk else 0

    # --- RR 10 ---
    rr_pts = 0
    if rr >= 2.5:
        rr_pts = 10
    elif rr >= 2.0:
        rr_pts = 8
    elif rr >= MIN_RR:
        rr_pts = 6
    else:
        # fail hard quality gate later
        rr_pts = 0
    score += rr_pts

    # News confluence bonus (capped)
    nb = max(0, min(int(news_bonus), NEWS_SCORE_BONUS_MAX))
    score += nb
    if nb:
        reasons.append(f"News confluence +{nb}")

    score = int(max(0, min(100, score)))

    # Hard quality gates (never loosen risk)
    if rr < MIN_RR:
        return None
    if mom_pts < 5 and struct_pts < 8:
        return None  # no meaningful momentum or structure

    tier = None
    action = "none"
    if score >= A_PLUS_SCORE:
        tier = "A+"
        action = "signal"
    elif score >= MIN_SIGNAL_SCORE:
        tier = "A"
        action = "signal"
    elif score >= WATCHLIST_SCORE:
        tier = "WATCHLIST"
        action = "watchlist"
    else:
        return None

    model = "trend_continuation"
    if sweep and (choch or bos):
        model = "liquidity_reversal"
    elif fvg_ok and mom_pts >= 10:
        model = "pullback_momentum"
    elif mom_pts >= 15 and bos:
        model = "breakout_momentum"

    return {
        "pair": "XAUUSD",
        "direction": dir_label,
        "bias": direction,
        "score": score,
        "tier": tier,
        "action": action,
        "model": model,
        "reasons": reasons,
        "entry_zone": f"{el}-{eh}",
        "stop_loss": str(round(stop, 2)),
        "tp1": str(tp1),
        "tp2": str(tp2),
        "tp3": str(tp3),
        "rr": round(rr, 2),
        "structure_level": round(float(structure), 2),
        "htf": h4_bias,
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
