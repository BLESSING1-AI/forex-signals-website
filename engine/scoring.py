"""
Scoring:
- BTC: momentum OK but entry MUST stay near live price (no late chase)
- Gold: pullback / structure, H4 required, wide SL
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
    if (LONDON_START <= h < LONDON_END) or (NY_START <= h < NY_END):
        return 5
    return 0


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


def _h1_structure(h1: Optional[pd.DataFrame], direction: str) -> Optional[float]:
    if h1 is None or h1.empty or len(h1) < 20:
        return None
    return find_nearby_structure_level(h1, direction)


def _atr(df: pd.DataFrame, n: int = 14) -> float:
    if df is None or len(df) < n + 1:
        return 0.0
    h = df["high"].astype(float)
    l = df["low"].astype(float)
    c = df["close"].astype(float)
    tr = pd.concat(
        [(h - l), (h - c.shift(1)).abs(), (l - c.shift(1)).abs()],
        axis=1,
    ).max(axis=1)
    return float(tr.tail(n).mean())


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
    is_gold = symbol == "XAUUSD"
    require_htf = bool(meta.get("require_htf", is_gold))
    prefer_pullback = bool(meta.get("prefer_pullback", is_gold))
    allow_breakout = bool(meta.get("allow_breakout", not is_gold))

    if m15 is None or m15.empty or h4 is None or h4.empty:
        return None

    tf = m5 if m5 is not None and not m5.empty and len(m5) >= 10 else m15
    price = float(tf["close"].iloc[-1])

    h4_bias = determine_bias(h4)
    d1_bias = determine_bias(d1) if d1 is not None and not d1.empty else "neutral"
    h1_bias = determine_bias(h1) if h1 is not None and not h1.empty else "neutral"

    if require_htf and h4_bias not in ("bullish", "bearish"):
        print(f"{symbol}: no H4 bias — skip")
        return None

    if h4_bias in ("bullish", "bearish"):
        direction = h4_bias
    elif h1_bias in ("bullish", "bearish"):
        direction = h1_bias
    else:
        net5, _ = displacement_metrics(tf, 5)
        if abs(net5) < disp_ok:
            return None
        direction = "bullish" if net5 > 0 else "bearish"

    if is_gold and h1_bias in ("bullish", "bearish") and h1_bias != direction:
        print(f"{symbol}: H1 fights H4 — skip")
        return None

    dir_label = "BUY" if direction == "bullish" else "SELL"

    net2, rng2 = displacement_metrics(tf, 2)
    net3, rng3 = displacement_metrics(tf, 3)
    net5, rng5 = displacement_metrics(tf, 5)
    signed2 = net2 if direction == "bullish" else -net2
    signed3 = net3 if direction == "bullish" else -net3
    signed5 = net5 if direction == "bullish" else -net5

    structure = _h1_structure(h1, direction) if is_gold else None
    if structure is None:
        structure = find_nearby_structure_level(m15, direction)
    if structure is None:
        structure = (
            float(m15["low"].tail(20).min())
            if direction == "bullish"
            else float(m15["high"].tail(20).max())
        )

    atr15 = _atr(m15, 14)
    dyn_buf = sl_buffer
    if atr15 > 0:
        dyn_buf = max(sl_buffer, atr15 * (0.9 if is_gold else 0.6))

    last_body = float(tf["close"].iloc[-1] - tf["open"].iloc[-1])
    last_against = (direction == "bullish" and last_body < 0) or (
        direction == "bearish" and last_body > 0
    )
    if signed5 >= disp_strong * 1.3 and last_against:
        print(f"{symbol}: exhausted — skip")
        return None

    # LATE MOVE: already ran hard — don't sell/buy after the drop/rally
    if abs(signed5) >= disp_strong * 1.15 and abs(signed2) < disp_ok * 0.5:
        print(f"{symbol}: late after big move — skip")
        return None

    dist = abs(price - structure)
    if dist > dyn_buf * (2.2 if is_gold else 3.5) and signed5 >= disp_solid:
        print(f"{symbol}: extended from structure — skip")
        return None

    fresh = _fresh_break(tf, direction) or _fresh_break(m15, direction)
    bos = detect_bos(tf)
    choch = detect_choch(m15)
    sweep = detect_liquidity_sweep(tf) or detect_liquidity_sweep(m15)
    fvg = detect_fvg(tf) or detect_fvg(m15)
    engulf = detect_engulfing(tf) or detect_engulfing(m15)
    pin = detect_pin_bar(tf) or detect_pin_bar(m15)

    near = abs(price - structure) <= dyn_buf * 2.5

    breakout = (
        (signed2 >= disp_ok or signed3 >= disp_solid * 0.7)
        and signed5 < disp_strong * 1.5
        and (fresh or bos == direction or signed3 >= disp_solid)
    )

    if is_gold and prefer_pullback:
        quality = near or sweep == direction or engulf == direction or pin == direction
        if not quality:
            if not (choch == direction and h4_bias == direction and dist <= dyn_buf * 3):
                print(f"{symbol}: no pullback quality — skip")
                return None
        breakout = False

    if not allow_breakout:
        breakout = False

    reasons: List[str] = []
    score = 0

    struct_pts = 0
    if near:
        struct_pts += 10
        reasons.append("At structure")
    if sweep == direction:
        struct_pts += 12
        reasons.append("Sweep")
    if engulf == direction:
        struct_pts += 10
        reasons.append("Engulf")
    if pin == direction:
        struct_pts += 10
        reasons.append("Pin")
    if choch == direction:
        struct_pts += 10
        reasons.append("CHoCH")
    if fresh and not is_gold:
        struct_pts += 12
        reasons.append("Fresh break")
    elif bos == direction and not is_gold:
        struct_pts += 8
        reasons.append("BOS")
    if fvg and fvg.get("direction") == direction:
        struct_pts += 6
        reasons.append("FVG")
    struct_pts = min(24, struct_pts)
    score += struct_pts

    mom_pts = 0
    if not is_gold and breakout and signed3 >= disp_solid:
        mom_pts = 20
        reasons.append("Momentum breakout")
    elif signed2 >= disp_ok * 0.8 and signed5 < disp_strong * 1.1:
        mom_pts = 14
        reasons.append("Early impulse")
    elif signed5 >= disp_ok * 0.6:
        mom_pts = 10
        reasons.append("Directional")
    elif near and (engulf == direction or pin == direction):
        mom_pts = 12
        reasons.append("Rejection")
    else:
        mom_pts = 4
    score += mom_pts

    htf_pts = 0
    if h4_bias == direction and h1_bias == direction:
        htf_pts = 20
        reasons.append("H4+H1")
    elif h4_bias == direction:
        htf_pts = 14
        reasons.append("H4")
    elif h1_bias == direction:
        htf_pts = 10
        reasons.append("H1")
    elif d1_bias == direction:
        htf_pts = 6
        reasons.append("D1")
    score += htf_pts

    if require_htf and htf_pts < 14:
        return None

    fvg_ok = bool(fvg and fvg.get("direction") == direction)
    score += 6 if fvg_ok else 0

    avg_rng = float((m15["high"] - m15["low"]).tail(20).mean()) or 1
    if rng3 >= avg_rng * 1.1 or rng3 >= vol_abs_mid * 0.5:
        score += 5
    score += _session_points(session_mode)

    if is_gold and struct_pts < 12:
        return None

    # --- Entry MUST hug live price (fixes late/wrong zones) ---
    tick = max(price * 0.00005, 0.5) if symbol == "BTCUSD" else 0.5
    if symbol == "BTCUSD":
        # tight zone around current price only
        band = max(80.0, atr15 * 0.35 if atr15 else 100.0)
        if direction == "bullish":
            el = round(price - band * 0.35, decimals)
            eh = round(price + band * 0.15, decimals)
            stop = round(min(structure, el) - dyn_buf, decimals)
            if stop >= el:
                stop = round(el - dyn_buf, decimals)
        else:
            el = round(price - band * 0.15, decimals)
            eh = round(price + band * 0.35, decimals)
            stop = round(max(structure, eh) + dyn_buf, decimals)
            if stop <= eh:
                stop = round(eh + dyn_buf, decimals)
    else:
        if direction == "bullish":
            el = round(min(structure, price) - tick, decimals)
            eh = round(min(price + tick * 2, structure + dyn_buf * 0.6), decimals)
            if el > eh:
                el, eh = round(price - tick * 2, decimals), round(price + tick, decimals)
            stop = round(min(structure, el) - dyn_buf, decimals)
            if stop >= el:
                stop = round(el - dyn_buf, decimals)
        else:
            el = round(max(price - tick * 2, structure - dyn_buf * 0.6), decimals)
            eh = round(max(structure, price) + tick, decimals)
            if el > eh:
                el, eh = round(price - tick, decimals), round(price + tick * 2, decimals)
            stop = round(max(structure, eh) + dyn_buf, decimals)
            if stop <= eh:
                stop = round(eh + dyn_buf, decimals)

    mid = (el + eh) / 2.0

    # Hard reject: mid entry too far from live price
    max_away = price * 0.004 if symbol == "BTCUSD" else max(12.0, price * 0.003)
    if abs(mid - price) > max_away:
        print(f"{symbol}: entry mid {mid} far from price {price} — late skip")
        return None

    risk = abs(mid - stop)
    if risk < risk_min:
        stop = (
            round(mid - risk_min, decimals)
            if direction == "bullish"
            else round(mid + risk_min, decimals)
        )
        risk = abs(mid - stop)
    if risk > risk_max:
        stop = (
            round(mid - risk_max * 0.5, decimals)
            if direction == "bullish"
            else round(mid + risk_max * 0.5, decimals)
        )
        risk = abs(mid - stop)

    r1 = max(MIN_RR, 1.8 if is_gold else 1.6)
    if direction == "bullish":
        tp1 = round(mid + risk * r1, decimals)
        tp2 = round(mid + risk * 3.0, decimals)
        tp3 = round(mid + risk * 5.0, decimals)
    else:
        # sell: TP1 closest (highest), TP3 furthest (lowest)
        tp1 = round(mid - risk * r1, decimals)
        tp2 = round(mid - risk * 3.0, decimals)
        tp3 = round(mid - risk * 5.0, decimals)

    # Sanity: TPs on correct side of entry
    if direction == "BUY" and not (tp1 > mid and tp3 > tp1):
        return None
    if direction == "SELL" and not (tp1 < mid and tp3 < tp1):
        return None

    rr = round(abs(tp1 - mid) / risk, 2) if risk else 0.0
    if rr + 1e-9 < MIN_RR:
        return None
    score += 6

    nb = max(0, min(int(news_bonus), NEWS_SCORE_BONUS_MAX))
    score += nb
    score = int(max(0, min(100, score)))

    min_sym = int(meta.get("min_score", MIN_SIGNAL_SCORE))
    if score >= A_PLUS_SCORE:
        tier, action = "A+", "signal"
    elif score >= min_sym:
        tier, action = "A", "signal"
    elif score >= WATCHLIST_SCORE:
        tier, action = "WATCHLIST", "watchlist"
    else:
        return None

    model = "gold_pullback" if is_gold else ("momentum_breakout" if breakout else "continuation")
    if near and not is_gold:
        model = "pullback"
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
            "near": near,
            "sweep": sweep,
            "engulf": engulf,
            "pin": pin,
            "choch": choch,
            "fvg": fvg_ok,
            "h4": h4_bias,
            "h1": h1_bias,
        },
    }
