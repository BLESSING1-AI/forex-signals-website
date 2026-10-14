"""Telegram — short messages only"""
import requests
from datetime import datetime
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID

def send_message(text: str) -> bool:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={
                "chat_id": TELEGRAM_CHANNEL_ID,
                "text": text.strip(),
                "disable_web_page_preview": True,
            },
            timeout=15,
        )
        ok = resp.json().get("ok", False)
        if ok:
            print(f"[{datetime.utcnow().isoformat()}] posted")
        else:
            print("TG error:", resp.json())
        return ok
    except Exception as e:
        print("Send failed:", e)
        return False

def format_signal(signal: dict) -> str:
    """Ultra-short technical signal."""
    d = signal["direction"].upper()
    gold = "BUY GOLD" if d == "BUY" else "SELL GOLD"
    return (
        f"⚡ {gold}\n"
        f"In: {signal['entry_zone']}\n"
        f"SL: {signal['stop_loss']}\n"
        f"TP1: {signal['tp1']} | TP2: {signal['tp2']} | TP3: {signal['tp3']}\n"
        f"Risk 1% · PA setup"
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
        f"Small size · quick scalp · Risk 0.5%"
    )

def send_momentum(signal: dict) -> bool:
    return send_message(format_momentum(signal))
