"""
Day-trading + momentum breakouts.
Gold: weekdays 05–21 UTC (07:00–23:00 SAST). BTC: always.
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
    NY_END,
)

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
    # Continuous window morning → NY close
    return LONDON_START <= h < NY_END


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
        print(f"{symbol}: outside session ({LONDON_START}-{NY_END} UTC)")
        return None

    max_daily = int(meta.get("max_daily", 5))
    if signals_posted_today(symbol) >= max_daily:
        print(f"{symbol}: daily limit")
        return None
    if not cooldown_ok(symbol, SIGNAL_COOLDOWN_MINUTES):
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

    print(
        f"SETUP {symbol} {setup['tier']} {setup['direction']} "
        f"{setup['score']} {setup.get('model')} {setup.get('reasons')}"
    )

    if is_duplicate(setup):
        print(f"{symbol}: duplicate")
        return None

    setup["invalidation"] = _invalidation(setup)
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
