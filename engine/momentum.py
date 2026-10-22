"""
Scored momentum for all configured symbols (XAUUSD, BTCUSD, …).
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
)

try:
    from signals_writer import record_signal
except Exception:
    record_signal = None


def generate_for_symbol(symbol: str) -> Optional[Dict[str, Any]]:
    if NEWS_BLACKOUT:
        return None
    wd = datetime.now(timezone.utc).weekday()
    meta = SYMBOLS.get(symbol, {})
    if meta.get("session_mode") == "fx" and wd >= 5:
        return None

    max_daily = int(meta.get("max_daily", 3))
    if signals_posted_today(symbol) >= max_daily:
        print(f"{symbol}: daily limit reached")
        return None
    if not cooldown_ok(symbol, SIGNAL_COOLDOWN_MINUTES):
        print(f"{symbol}: cooldown active")
        return None

    data = get_multi_timeframe_data(symbol)
    d1, h4, m15, m5 = data.get("1d"), data.get("4h"), data.get("15m"), data.get("5m")
    if any(x is None or (hasattr(x, "empty") and x.empty) for x in [h4, m15]):
        return None

    setup = score_setup(d1, h4, m15, m5, news_bonus=0, symbol=symbol)
    if not setup:
        print(f"{symbol}: score below threshold / no lean")
        return None

    if is_duplicate(setup):
        print(f"{symbol}: duplicate fingerprint")
        return None

    print(
        f"SCORED {symbol} {setup['tier']} {setup['direction']} "
        f"score={setup['score']} model={setup['model']} RR={setup['rr']}"
    )
    return setup


def run_momentum() -> bool:
    any_trade = False
    for symbol in SYMBOLS.keys():
        try:
            setup = generate_for_symbol(symbol)
        except Exception as e:
            print(f"{symbol} momentum error:", e)
            continue
        if not setup:
            continue

        if setup.get("action") == "watchlist":
            if send_watchlist(setup):
                mark_fingerprint(setup)
                if record_signal:
                    try:
                        record_signal(setup, watchlist=True)
                    except Exception as e:
                        print("writer", e)
            continue

        if setup.get("action") != "signal" or setup["score"] < MIN_SIGNAL_SCORE:
            continue

        if send_scored_signal(setup):
            mark_signal_posted(symbol)
            mark_cooldown(symbol)
            mark_fingerprint(setup)
            if record_signal:
                try:
                    record_signal(setup, watchlist=False)
                except Exception as e:
                    print("writer", e)
            print(f"{symbol} trade posted score={setup['score']}")
            any_trade = True
    return any_trade
