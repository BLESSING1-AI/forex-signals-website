"""
Main runner — scored momentum/PA + separate news event engine.
NO forced daily signals. Quality score drives sends.
"""
from datetime import datetime, timezone

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
    NEWS_BLACKOUT,
    LONDON_START,
    LONDON_END,
    NY_START,
    NY_END,
)

try:
    from event_engine import run_event_cycle
except Exception:
    run_event_cycle = None

try:
    from momentum import run_momentum
except Exception:
    run_momentum = None


def is_session_active() -> bool:
    hour = datetime.now(timezone.utc).hour
    return (LONDON_START <= hour < LONDON_END) or (NY_START <= hour < NY_END)


def generate_pa_signal():
    """Secondary scored pass (same scorer as momentum — shared quality)."""
    if NEWS_BLACKOUT or not is_session_active():
        return None
    if signals_posted_today("XAUUSD") >= MAX_DAILY_SIGNALS_XAU:
        return None
    if not cooldown_ok("XAUUSD", SIGNAL_COOLDOWN_MINUTES):
        return None

    data = get_multi_timeframe_data()
    setup = score_setup(
        data.get("1d"), data.get("4h"), data.get("15m"), data.get("5m"), news_bonus=0
    )
    if not setup:
        return None
    if is_duplicate(setup):
        return None
    return setup


def run_once():
    print(f"\n=== Run @ {datetime.now(timezone.utc).isoformat()} ===")
    print("XAU signals today:", signals_posted_today("XAUUSD"))

    # NEWS — separate engine, unchanged philosophy
    if run_event_cycle:
        try:
            print("Events:", run_event_cycle())
        except Exception as e:
            print("Event error:", e)

    # MOMENTUM scored engine
    posted = False
    if run_momentum:
        try:
            posted = bool(run_momentum())
        except Exception as e:
            print("Momentum error:", e)

    if posted:
        return

    # Shared scorer path (if momentum skipped e.g. import issue)
    setup = generate_pa_signal()
    if not setup:
        print("No scored setup this cycle")
        return

    if setup["action"] == "watchlist":
        send_watchlist(setup)
        mark_fingerprint(setup)
        return

    if setup["score"] < MIN_SIGNAL_SCORE:
        return

    if send_scored_signal(setup):
        mark_signal_posted("XAUUSD")
        mark_cooldown("XAUUSD")
        mark_fingerprint(setup)
        print("PA scored posted", setup["score"], setup["tier"])


if __name__ == "__main__":
    run_once()
