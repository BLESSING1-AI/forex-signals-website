"""
Day-trading engine.
Gold: strict London/NY pullback quality (few signals, wide SL).
BTC: momentum allowed, more frequent.
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
    """Gold only in London or NY — avoid Asia chop."""
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
        cd = max(cd, 90)  # gold: wait longer between signals
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

    # Per-symbol min score (gold stricter)
    min_sc = int(meta.get("min_score", MIN_SIGNAL_SCORE))
    if setup.get("action") == "signal" and setup.get("score", 0) < min_sc:
        print(f"{symbol}: score {setup['score']} < min {min_sc} → watchlist")
        setup["action"] = "watchlist"
        setup["tier"] = "WATCHLIST"

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

        if setup.get("action") != "signal":
            continue

        meta = SYMBOLS.get(symbol, {})
        min_sc = int(meta.get("min_score", MIN_SIGNAL_SCORE))
        if setup["score"] < min_sc:
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
