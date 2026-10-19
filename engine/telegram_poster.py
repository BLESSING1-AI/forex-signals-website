"""Telegram poster — always uses working channel ID"""
import requests
from datetime import datetime
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID

# Hard fallback if secrets are wrong
CHANNEL_FALLBACK = "-1004499950812"

def _chat_id() -> str:
    cid = str(TELEGRAM_CHANNEL_ID or "").strip()
    if cid.lstrip("-").isdigit():
        return cid
    return CHANNEL_FALLBACK

def send_message(text: str) -> bool:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    chat = _chat_id()
    try:
        resp = requests.post(
            url,
            json={
                "chat_id": chat,
                "text": text.strip(),
                "disable_web_page_preview": True,
            },
            timeout=15,
        )
        data = resp.json()
        if data.get("ok"):
            return True
        print("TG error:", data)
        # one retry with fallback
        if chat != CHANNEL_FALLBACK:
            resp2 = requests.post(
                url,
                json={
                    "chat_id": CHANNEL_FALLBACK,
                    "text": text.strip(),
                    "disable_web_page_preview": True,
                },
                timeout=15,
            )
            return resp2.json().get("ok", False)
        return False
    except Exception as e:
        print("Send failed:", e)
        return False

def format_signal(signal: dict) -> str:
    d = signal["direction"].upper()
    gold = "BUY GOLD" if d == "BUY" else "SELL GOLD"
    return (
        f"⚡ {gold}\n"
        f"In: {signal['entry_zone']}\n"
        f"SL: {signal['stop_loss']}\n"
        f"TP1: {signal['tp1']} | TP2: {signal['tp2']} | TP3: {signal['tp3']}\n"
        f"Risk 1% · Daily PA"
    )

def send_signal(signal: dict) -> bool:
    return send_message(format_signal(signal))

def format_momentum(signal: dict) -> str:
    d = signal["direction"].upper()
    gold = "BUY GOLD" if d == "BUY" else "SELL GOLD"
    return (
        f"🔥 MOMENTUM {gold}\n"
        f"In: {signal['entry_zone']}\n"
        f"SL: {signal['stop_loss']}\n"
        f"TP1: {signal['tp1']} | TP2: {signal['tp2']}\n"
        f"Risk 0.5% · scalp"
    )

def send_momentum(signal: dict) -> bool:
    return send_message(format_momentum(signal))
