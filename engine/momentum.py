"""
Day-trading engine with hybrid AI verification.
Deterministic score/levels first → regime → Gemini gate → Telegram.
Gold: London/NY pullback. BTC: momentum allowed, weekends OK.
"""
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from data_fetcher import get_multi_timeframe_data
from scoring import score_setup
from telegram_poster import send_scored_signal, send_watchlist
from state_store import (
    signals_posted_today,
    mark_signal_posted,
    cooldown_ok,
    mark_cooldown,
    is_duplicate,
    mark_fingerprint,
)
from config import (
    SYMBOLS,
    SIGNAL_COOLDOWN_MINUTES,
    MIN_SIGNAL_SCORE,
    NEWS_BLACKOUT,
    LONDON_START,
    LONDON_END,
    NY_START,
    NY_END,
    AI_STRICT,
    DRY_RUN,
)

try:
    from regime import detect_regime
except Exception:
    detect_regime = None

try:
    from ai_verifier import verify_setup, apply_ai_gate
except Exception:
    verify_setup = None
    apply_ai_gate = None

try:
    from signals_writer import record_signal
except Exception:
    record_signal = None

try:
    from trade_manager import register_open_trade
except Exception:
    register_open_trade = None


def _in_gold_session() -> bool:
    now = datetime.now(timezone.utc)
    if now.weekday() >= 5:
        return False
    h = now.hour
    return (LONDON_START <= h < LONDON_END) or (NY_START <= h < NY_END)


def _invalidation(setup: dict) -> str:
    d = setup.get("direction", "BUY")
    sl = setup.get("stop_loss")
    return f"close below {sl}" if d == "BUY" else f"close above {sl}"


def generate_for_symbol(symbol: str) -> Optional[Dict[str, Any]]:
    if NEWS_BLACKOUT:
        return None

    meta = SYMBOLS.get(symbol, {})
    mode = meta.get("session_mode", "fx")

    if mode == "fx" and not _in_gold_session():
        print(f"{symbol}: outside London/NY")
        return None

    max_daily = int(meta.get("max_daily", 3))
    if signals_posted_today(symbol) >= max_daily:
        print(f"{symbol}: daily limit {max_daily}")
        return None

    cd = SIGNAL_COOLDOWN_MINUTES
    if symbol == "XAUUSD":
        cd = max(cd, 90)
    if not cooldown_ok(symbol, cd):
        print(f"{symbol}: cooldown")
        return None

    data = get_multi_timeframe_data(symbol)
    d1, h4, h1 = data.get("1d"), data.get("4h"), data.get("1h")
    m15, m5 = data.get("15m"), data.get("5m")
    if any(x is None or (hasattr(x, "empty") and x.empty) for x in [h4, m15]):
        print(f"{symbol}: missing bars")
        return None

    setup = score_setup(d1, h4, m15, m5, news_bonus=0, symbol=symbol, h1=h1)
    if not setup:
        print(f"{symbol}: no setup")
        return None

    min_sc = int(meta.get("min_score", MIN_SIGNAL_SCORE))
    if setup.get("action") == "signal" and setup.get("score", 0) < min_sc:
        setup["action"] = "watchlist"
        setup["tier"] = "WATCHLIST"

    # Regime (deterministic)
    regime: Dict[str, Any] = {}
    if detect_regime:
        try:
            regime = detect_regime(m15, h1=h1, h4=h4) or {}
        except Exception as e:
            print("regime error", e)
            regime = {"regime": "unknown"}
    setup["regime"] = regime.get("regime", "unknown")
    setup["regime_detail"] = regime

    # Strategy label from model
    setup["strategy"] = setup.get("model") or "price_action"

    print(
        f"SETUP {symbol} {setup.get('tier')} {setup.get('direction')} "
        f"{setup.get('score')} {setup.get('strategy')} regime={setup.get('regime')}"
    )

    if is_duplicate(setup):
        print(f"{symbol}: duplicate")
        return None

    setup["invalidation"] = _invalidation(setup)

    # Gemini verification — never invents prices
    if setup.get("action") == "signal" and verify_setup and apply_ai_gate:
        try:
            ai = verify_setup(setup, regime)
            setup = apply_ai_gate(setup, ai, strict=AI_STRICT)
            print(
                f"AI {symbol} decision={ai.get('decision')} "
                f"conf={ai.get('confidence')} status={ai.get('ai_status')}"
            )
        except Exception as e:
            print("AI error", e)
            if AI_STRICT:
                setup["action"] = "reject"
                setup["tier"] = "REJECT"
                setup["ai"] = {
                    "decision": "REJECT",
                    "confidence": 0,
                    "explanation": f"AI error: {e}",
                    "ai_status": "error",
                }

    return setup


def run_momentum() -> bool:
    any_trade = False
    for symbol in SYMBOLS.keys():
        try:
            setup = generate_for_symbol(symbol)
        except Exception as e:
            print(f"{symbol} error:", e)
            continue
        if not setup:
            continue

        action = setup.get("action")

        if action == "reject":
            print(f"{symbol}: AI/engine REJECT — not sent")
            continue

        if action == "watchlist":
            if DRY_RUN:
                print("DRY_RUN watchlist", setup.get("pair"), setup.get("direction"))
                continue
            if send_watchlist(setup):
                mark_fingerprint(setup)
                if record_signal:
                    try:
                        record_signal(setup, watchlist=True)
                    except Exception as e:
                        print("writer", e)
            continue

        if action != "signal":
            continue

        meta = SYMBOLS.get(symbol, {})
        min_sc = int(meta.get("min_score", MIN_SIGNAL_SCORE))
        if setup.get("score", 0) < min_sc:
            continue

        if DRY_RUN:
            print(
                "DRY_RUN signal",
                setup.get("pair"),
                setup.get("direction"),
                setup.get("score"),
                (setup.get("ai") or {}).get("decision"),
            )
            any_trade = True
            continue

        if send_scored_signal(setup):
            mark_signal_posted(symbol)
            mark_cooldown(symbol)
            mark_fingerprint(setup)
            if register_open_trade:
                try:
                    register_open_trade(setup)
                except Exception as e:
                    print("register", e)
            if record_signal:
                try:
                    record_signal(setup, watchlist=False)
                except Exception as e:
                    print("writer", e)
            any_trade = True
            print(f"SENT {symbol} {setup['direction']} {setup['score']}")
    return any_trade
