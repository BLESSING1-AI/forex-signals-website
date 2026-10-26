"""Telegram — multi-symbol scored signals + invalidation line"""
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

def _invalidation_line(setup: dict) -> str:
    inv = setup.get("invalidation")
    if inv:
        return f"⚠️ Invalid: {inv}"
    d = setup.get("direction", "BUY")
    sl = setup.get("stop_loss", "?")
    if d == "BUY":
        return f"⚠️ Invalid: close below SL {sl}"
    return f"⚠️ Invalid: close above SL {sl}"

def send_scored_signal(setup: dict) -> bool:
    pair = setup.get("pair", "XAUUSD")
    d = setup["direction"]
    tier = setup.get("tier", "A")
    score = setup.get("score", 0)
    icon = "🔥" if tier == "A+" else "🟢"
    conf = "HIGH" if score >= 85 else "GOOD"
    reasons = setup.get("reasons") or []
    reason_txt = "; ".join(reasons[:5]) if reasons else setup.get("model", "")
    c = setup.get("confirmations") or {}

    lines = [
        f"{icon} {pair} {d} — {tier} SETUP",
        f"📊 Score: {score}/100",
        f"📈 Bias: {str(setup.get('bias', d)).title()}",
        f"⚡ Model: {setup.get('model', 'momentum')}",
        f"🏗 Structure: {'BOS' if c.get('bos') else '—'}",
        f"💧 Liquidity: {'Sweep' if c.get('sweep') else '—'}",
        f"🧩 FVG: {'Yes' if c.get('fvg') else '—'}",
        f"📍 Entry: {setup['entry_zone']}",
        f"🛑 SL: {setup['stop_loss']}",
        f"🎯 TP1: {setup['tp1']} | TP2: {setup['tp2']} | TP3: {setup['tp3']}",
        f"📐 RR: 1:{setup.get('rr', '—')}",
        f"🔥 Confidence: {conf}",
        f"Risk 1%",
        _invalidation_line(setup),
        f"After TP1 → SL to BE",
        f"Reason: {reason_txt}",
    ]
    return send_message("\n".join(lines))

def send_watchlist(setup: dict) -> bool:
    pair = setup.get("pair", "XAUUSD")
    d = setup["direction"]
    score = setup.get("score", 0)
    waiting = []
    c = setup.get("confirmations") or {}
    if not c.get("bos"):
        waiting.append("BOS confirmation")
    if not c.get("fvg"):
        waiting.append("FVG / cleaner zone")
    if setup.get("momentum_pts", 0) < 15:
        waiting.append("Stronger continuation")
    if not waiting:
        waiting = ["Retest", "Strong continuation candle"]

    lines = [
        f"👀 {pair} WATCHLIST",
        f"Developing {d} setup",
        f"Score: {score}/100",
        f"Waiting for:",
    ]
    for w in waiting[:4]:
        lines.append(f"• {w}")
    lines.append("No entry yet.")
    return send_message("\n".join(lines))

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
