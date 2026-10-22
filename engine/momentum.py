"""
Scored momentum engine — flexible confirmation combinations.
Tiers: A+ / A send trade; WATCHLIST alert only; below 68 skip.
News engine stays separate (event_engine).
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
    MAX_DAILY_SIGNALS_XAU,
    SIGNAL_COOLDOWN_MINUTES,
    MIN_SIGNAL_SCORE,
    WATCHLIST_SCORE,
    NEWS_BLACKOUT,
)


def generate_momentum() -> Optional[Dict[str, Any]]:
    if NEWS_BLACKOUT:
        return None
    if datetime.now(timezone.utc).weekday() >= 5:
        return None

    symbol = "XAUUSD"
    if signals_posted_today(symbol) >= MAX_DAILY_SIGNALS_XAU:
        print("Momentum: daily limit reached")
        return None
    if not cooldown_ok(symbol, SIGNAL_COOLDOWN_MINUTES):
        print("Momentum: cooldown active")
        return None

    data = get_multi_timeframe_data()
    d1, h4, m15, m5 = data.get("1d"), data.get("4h"), data.get("15m"), data.get("5m")
    if any(x is None or (hasattr(x, "empty") and x.empty) for x in [h4, m15]):
        return None

    setup = score_setup(d1, h4, m15, m5, news_bonus=0)
    if not setup:
        print("Momentum: score below threshold / no lean")
        return None

    if is_duplicate(setup):
        print("Momentum: duplicate fingerprint")
        return None

    print(
        f"SCORED {setup['tier']} {setup['direction']} score={setup['score']} "
        f"model={setup['model']} RR={setup['rr']}"
    )
    return setup


def run_momentum() -> bool:
    setup = generate_momentum()
    if not setup:
        return False

    action = setup.get("action")
    if action == "watchlist":
        ok = send_watchlist(setup)
        if ok:
            mark_fingerprint(setup)  # avoid spam watchlist same zone
        return False  # does not count as full trade signal

    if action != "signal":
        return False

    if setup["score"] < MIN_SIGNAL_SCORE:
        return False

    ok = send_scored_signal(setup)
    if ok:
        mark_signal_posted("XAUUSD")
        mark_cooldown("XAUUSD")
        mark_fingerprint(setup)
        print(f"Momentum trade posted score={setup['score']}")
        return True
    return False
