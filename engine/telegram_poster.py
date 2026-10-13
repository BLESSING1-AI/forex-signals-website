"""
Telegram poster - exact format from framework
"""
import requests
from datetime import datetime
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID

def format_signal(signal: dict) -> str:
    direction = signal["direction"].upper()
    pair = signal["pair"]
    return f"""🚨 PRICE ACTION SIGNAL: {direction} {pair} 🚨

📍 Entry Zone: {signal['entry_zone']}
🛑 Stop Loss: {signal['stop_loss']} (Structure SL)

🎯 Take Profit 1: {signal['tp1']} (Partial close + Move SL to BE)
🎯 Take Profit 2: {signal['tp2']}
🎯 Take Profit 3: {signal['tp3']}

📊 Setup Context:
{signal.get('context', '• Multi-timeframe price action alignment')}
• Recommended Risk: {signal.get('risk', '1%')} per trade

⚠️ Educational only. Manage your risk.""".strip()

def send_signal(signal: dict) -> bool:
    text = format_signal(signal)
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHANNEL_ID,
        "text": text,
        "disable_web_page_preview": True
    }
    try:
        resp = requests.post(url, json=payload, timeout=15)
        data = resp.json()
        if data.get("ok"):
            print(f"[{datetime.utcnow().isoformat()}] Signal posted")
            return True
        print("Telegram error:", data)
        return False
    except Exception as e:
        print("Send failed:", e)
        return False

def send_message(text: str) -> bool:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(url, json={"chat_id": TELEGRAM_CHANNEL_ID, "text": text}, timeout=15)
        return resp.json().get("ok", False)
    except Exception:
        return False
