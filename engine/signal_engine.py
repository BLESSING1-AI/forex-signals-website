"""
Main runner — multi-symbol scored momentum + gold news events.
"""
from datetime import datetime, timezone

from state_store import signals_posted_today
from config import SYMBOLS

try:
    from event_engine import run_event_cycle
except Exception:
    run_event_cycle = None

try:
    from momentum import run_momentum
except Exception:
    run_momentum = None


def run_once():
    print(f"\n=== Run @ {datetime.now(timezone.utc).isoformat()} ===")
    for sym in SYMBOLS:
        print(f"{sym} signals today:", signals_posted_today(sym))

    # NEWS — gold/USD focused, separate engine
    if run_event_cycle:
        try:
            print("Events:", run_event_cycle())
        except Exception as e:
            print("Event error:", e)

    if run_momentum:
        try:
            run_momentum()
        except Exception as e:
            print("Momentum error:", e)
    else:
        print("Momentum module unavailable")


if __name__ == "__main__":
    run_once()
