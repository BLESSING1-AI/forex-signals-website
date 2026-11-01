"""Telegram — short day-trade signals + event trains"""
import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID

CHANNEL_FALLBACK = "-1004499950812"


def _chat_id() -> str:
    cid = str(TELEGRAM_CHANNEL_ID or "").strip()
    if cid.lstrip("-").isdigit():
        return cid
    return CHANNEL_FALLBACK


def send_message(text: str) -> bool:
    if not TELEGRAM_BOT_TOKEN:
        print("No TELEGRAM_BOT_TOKEN")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    chat = _chat_id()
    try:
        resp = requests.post(
            url,
            json={"chat_id": chat, "text": text.strip(), "disable_web_page_preview": True},
            timeout=15,
        )
        data = resp.json()
        if data.get("ok"):
            return True
        print("TG error:", data)
        if chat != CHANNEL_FALLBACK:
            r2 = requests.post(
                url,
                json={
                    "chat_id": CHANNEL_FALLBACK,
                    "text": text.strip(),
                    "disable_web_page_preview": True,
                },
                timeout=15,
            )
            return r2.json().get("ok", False)
        return False
    except Exception as e:
        print("Send failed:", e)
        return False


def send_scored_signal(setup: dict) -> bool:
    """Short day-trade format (same style as manual signals)."""
    pair = setup.get("pair", "XAUUSD")
    d = setup["direction"]
    tier = setup.get("tier", "A")
    score = setup.get("score", 0)
    icon = "🔥" if tier == "A+" else "⚡"
    reasons = setup.get("reasons") or []
    why = reasons[0] if reasons else setup.get("model", "")

    lines = [
        f"{icon} {pair} {d}",
        f"In: {setup['entry_zone']}",
        f"SL: {setup['stop_loss']}",
        f"TP1: {setup['tp1']} | TP2: {setup['tp2']} | TP3: {setup['tp3']}",
        f"Risk 1% · {tier} {score}",
    ]
    if why:
        lines.append(str(why))
    return send_message("\n".join(lines))


def send_watchlist(setup: dict) -> bool:
    pair = setup.get("pair", "XAUUSD")
    d = setup["direction"]
    score = setup.get("score", 0)
    return send_message(
        f"👀 {pair} WATCH {d}\n"
        f"Score {score} · waiting confirmation\n"
        f"No entry yet"
    )


def format_signal(signal: dict) -> str:
    pair = signal.get("pair", "XAUUSD")
    d = signal["direction"].upper()
    return (
        f"⚡ {pair} {d}\n"
        f"In: {signal['entry_zone']}\n"
        f"SL: {signal['stop_loss']}\n"
        f"TP1: {signal['tp1']} | TP2: {signal['tp2']} | TP3: {signal['tp3']}\n"
        f"Risk 1%"
    )


def send_signal(signal: dict) -> bool:
    return send_message(format_signal(signal))


def send_momentum(signal: dict) -> bool:
    if "score" in signal:
        return send_scored_signal(signal)
    return send_message(format_signal(signal))
