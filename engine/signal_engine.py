"""Main runner — lifecycle + news + momentum + stats."""
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

try:
    from trade_manager import manage_open_trades
except Exception:
    manage_open_trades = None

try:
    from stats import maybe_send_weekly_stats, quiet_day_note
except Exception:
    maybe_send_weekly_stats = None
    quiet_day_note = None


def run_once():
    print(f"\n=== Run @ {datetime.now(timezone.utc).isoformat()} ===")
    for sym in SYMBOLS:
        print(f"{sym} today:", signals_posted_today(sym))

    # 1) Manage open trades (TP/SL/BE)
    if manage_open_trades:
        try:
            ev = manage_open_trades()
            if ev:
                print("Lifecycle:", ev)
        except Exception as e:
            print("Lifecycle error:", e)

    # 2) News (gold/USD)
    if run_event_cycle:
        try:
            print("Events:", run_event_cycle())
        except Exception as e:
            print("Event error:", e)

    # 3) New setups
    any_trade = False
    if run_momentum:
        try:
            any_trade = bool(run_momentum())
        except Exception as e:
            print("Momentum error:", e)

    # 4) Quiet day + weekly stats
    if quiet_day_note:
        try:
            quiet_day_note(len(SYMBOLS), any_trade)
        except Exception as e:
            print("quiet", e)
    if maybe_send_weekly_stats:
        try:
            maybe_send_weekly_stats()
        except Exception as e:
            print("weekly", e)


if __name__ == "__main__":
    run_once()
