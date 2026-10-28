"""Weekly performance summary + quiet day."""
from datetime import datetime, timezone, timedelta
from state_store import _load_raw, load_sent, save_sent
from telegram_poster import send_message


def _week_key() -> str:
    now = datetime.now(timezone.utc)
    return f"WEEKLY:{now.isocalendar()[0]}-W{now.isocalendar()[1]}"


def maybe_send_weekly_stats() -> bool:
    now = datetime.now(timezone.utc)
    k = _week_key()
    sent = load_sent()
    if k in sent:
        return False

    hour = now.hour
    wd = now.weekday()
    if not ((wd == 0 and 7 <= hour <= 10) or (wd == 4 and hour >= 18)):
        return False

    data = _load_raw()
    closed = data.get("closed_trades") or []
    cutoff = now - timedelta(days=7)
    recent = []
    for t in closed:
        try:
            ts = datetime.fromisoformat(str(t.get("closed_at", "")).replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts >= cutoff:
                recent.append(t)
        except Exception:
            continue

    if not recent:
        msg = (
            "📊 WEEKLY STATS\n"
            "No closed trades logged this week.\n"
            "Engine still scanning · quality over quantity."
        )
    else:
        wins = [t for t in recent if float(t.get("result_r") or 0) > 0]
        losses = [t for t in recent if float(t.get("result_r") or 0) <= 0]
        avg_r = sum(float(t.get("result_r") or 0) for t in recent) / len(recent)
        msg = (
            f"📊 WEEKLY STATS\n"
            f"Closed: {len(recent)}\n"
            f"Wins: {len(wins)} · Losses: {len(losses)}\n"
            f"Win rate: {100 * len(wins) / len(recent):.0f}%\n"
            f"Avg R: {avg_r:.2f}\n"
            f"Educational only · past ≠ future"
        )

    if send_message(msg):
        sent.add(k)
        save_sent(sent)
        return True
    return False


def quiet_day_note(symbols_checked: int, any_signal: bool) -> bool:
    if any_signal:
        return False
    now = datetime.now(timezone.utc)
    if now.weekday() >= 5:
        return False
    if not (14 <= now.hour <= 17):
        return False
    day = now.date().isoformat()
    k = f"QUIET:{day}"
    sent = load_sent()
    if k in sent:
        return False
    from state_store import signals_posted_today
    from config import SYMBOLS
    total = sum(signals_posted_today(s) for s in SYMBOLS)
    if total > 0:
        return False
    msg = (
        "⏸ NO A-SETUP YET\n"
        "Scanning XAU · BTC\n"
        "Waiting for score ≥75 · not forcing trades"
    )
    if send_message(msg):
        sent.add(k)
        save_sent(sent)
        return True
    return False
