"""Poll Telegram for /status /last /stats (channel or DM to bot)."""
from datetime import datetime, timezone
from typing import Optional
import requests

from config import TELEGRAM_BOT_TOKEN
from state_store import _load_raw, signals_posted_today
from config import SYMBOLS
from telegram_poster import send_message

OFFSET_KEY = "tg_update_offset"


def _get_offset() -> int:
    data = _load_raw()
    return int(data.get(OFFSET_KEY) or 0)


def _set_offset(n: int) -> None:
    from state_store import _save_raw
    data = _load_raw()
    data[OFFSET_KEY] = n
    _save_raw(data)


def _reply(chat_id: str, text: str) -> None:
    if not TELEGRAM_BOT_TOKEN:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=12,
        )
    except Exception as e:
        print("cmd reply", e)


def _status_text() -> str:
    data = _load_raw()
    opens = [t for t in (data.get("open_trades") or []) if t.get("status") == "open"]
    lines = ["📡 ENGINE STATUS", f"Time: {datetime.now(timezone.utc).strftime('%H:%M UTC')}"]
    for s in SYMBOLS:
        lines.append(f"{s} today: {signals_posted_today(s)}")
    lines.append(f"Open trades: {len(opens)}")
    for t in opens[:5]:
        lines.append(f"• {t.get('pair')} {t.get('direction')} BE={t.get('be')}")
    if not opens:
        lines.append("No open managed trades.")
    lines.append("Scanning XAU · BTC · ETH · quality score ≥75")
    return "\n".join(lines)


def _last_text() -> str:
    data = _load_raw()
    closed = data.get("closed_trades") or []
    opens = [t for t in (data.get("open_trades") or []) if t.get("status") == "open"]
    if opens:
        t = opens[-1]
        return (
            f"📌 LAST OPEN\n"
            f"{t.get('pair')} {t.get('direction')}\n"
            f"In ~{t.get('entry')} SL {t.get('sl')}\n"
            f"TP3 {t.get('tp3')} | TP2 {t.get('tp2')} | TP1 {t.get('tp1')}"
        )
    if closed:
        t = closed[-1]
        return (
            f"📌 LAST CLOSED\n"
            f"{t.get('pair')} {t.get('direction')} · {t.get('outcome')}\n"
            f"Result: {t.get('result_r')}R"
        )
    return "📌 No trades logged yet."


def _stats_text() -> str:
    data = _load_raw()
    closed = data.get("closed_trades") or []
    if not closed:
        return "📊 No closed trades logged yet."
    rs = [float(t.get("result_r") or 0) for t in closed[-50:]]
    wins = sum(1 for r in rs if r > 0)
    avg = sum(rs) / len(rs)
    return (
        f"📊 STATS (last {len(rs)})\n"
        f"Wins: {wins} · Losses: {len(rs) - wins}\n"
        f"Win rate: {100 * wins / len(rs):.0f}%\n"
        f"Avg R: {avg:.2f}\n"
        f"Educational only"
    )


def process_commands() -> int:
    if not TELEGRAM_BOT_TOKEN:
        return 0
    offset = _get_offset()
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates",
            params={"offset": offset, "timeout": 0, "limit": 20},
            timeout=15,
        )
        data = r.json()
    except Exception as e:
        print("getUpdates", e)
        return 0
    if not data.get("ok"):
        return 0
    n = 0
    max_id = offset
    for upd in data.get("result") or []:
        max_id = max(max_id, int(upd["update_id"]) + 1)
        msg = upd.get("message") or upd.get("channel_post") or {}
        text = (msg.get("text") or "").strip().lower()
        chat = msg.get("chat", {}).get("id")
        if not chat or not text:
            continue
        if text.startswith("/status"):
            _reply(chat, _status_text())
            n += 1
        elif text.startswith("/last"):
            _reply(chat, _last_text())
            n += 1
        elif text.startswith("/stats"):
            _reply(chat, _stats_text())
            n += 1
        elif text.startswith("/help"):
            _reply(chat, "Commands:\n/status\n/last\n/stats\n/help")
            n += 1
    if max_id > offset:
        _set_offset(max_id)
    return n
