"""
Trade lifecycle: TP hits, BE, SL, invalidation.
Persists open trades in state + website stats.
"""
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import json
import os

from data_fetcher import fetch_ohlc
from telegram_poster import send_message
from state_store import _load_raw, _save_raw

try:
    from signals_writer import record_trade_update, record_closed_trade
except Exception:
    record_trade_update = None
    record_closed_trade = None


def _mid_entry(zone: str) -> float:
    try:
        a, b = zone.split("-")
        return (float(a) + float(b)) / 2.0
    except Exception:
        return float(zone)


def register_open_trade(setup: Dict[str, Any]) -> None:
    data = _load_raw()
    opens = data.get("open_trades") or []
    tid = f"{setup.get('pair')}-{setup.get('direction')}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"
    trade = {
        "id": tid,
        "pair": setup.get("pair", "XAUUSD"),
        "direction": setup.get("direction", "BUY"),
        "entry": _mid_entry(str(setup.get("entry_zone", "0"))),
        "entry_zone": setup.get("entry_zone"),
        "sl": float(setup.get("stop_loss", 0)),
        "original_sl": float(setup.get("stop_loss", 0)),
        "tp1": float(setup.get("tp1", 0)),
        "tp2": float(setup.get("tp2", 0)),
        "tp3": float(setup.get("tp3", 0)),
        "tp1_hit": False,
        "tp2_hit": False,
        "tp3_hit": False,
        "be": False,
        "status": "open",
        "opened_at": datetime.now(timezone.utc).isoformat(),
        "invalidation": setup.get("invalidation") or "",
        "score": setup.get("score"),
        "tier": setup.get("tier"),
    }
    opens.append(trade)
    data["open_trades"] = opens[-40:]
    _save_raw(data)
    print("Registered open trade", tid)


def _last_price(pair: str) -> Optional[float]:
    df = fetch_ohlc(pair, "5m")
    if df is None or df.empty:
        df = fetch_ohlc(pair, "15m")
    if df is None or df.empty:
        return None
    return float(df["close"].iloc[-1])


def _r_multiple(trade: Dict, exit_px: float) -> float:
    risk = abs(trade["entry"] - trade["original_sl"])
    if risk <= 0:
        return 0.0
    if trade["direction"] == "BUY":
        return round((exit_px - trade["entry"]) / risk, 2)
    return round((trade["entry"] - exit_px) / risk, 2)


def manage_open_trades() -> List[str]:
    data = _load_raw()
    opens = data.get("open_trades") or []
    if not opens:
        return []

    closed_log = data.get("closed_trades") or []
    still_open = []
    events = []

    for t in opens:
        if t.get("status") != "open":
            continue
        pair = t["pair"]
        price = _last_price(pair)
        if price is None:
            still_open.append(t)
            continue

        d = t["direction"]
        hit_sl = price <= t["sl"] if d == "BUY" else price >= t["sl"]
        hit_tp1 = (not t.get("tp1_hit")) and (price >= t["tp1"] if d == "BUY" else price <= t["tp1"])
        hit_tp2 = (not t.get("tp2_hit")) and (price >= t["tp2"] if d == "BUY" else price <= t["tp2"])
        hit_tp3 = (not t.get("tp3_hit")) and (price >= t["tp3"] if d == "BUY" else price <= t["tp3"])

        # SL first (unless BE already and we're treating as protected)
        if hit_sl:
            r = _r_multiple(t, t["sl"])
            outcome = "BE" if t.get("be") and abs(r) < 0.15 else "SL"
            msg = (
                f"{'✅ BE EXIT' if outcome == 'BE' else '❌ SL HIT'} · {pair} {d}\n"
                f"Price ~{price}\n"
                f"Result: {r}R · {outcome}"
            )
            send_message(msg)
            t["status"] = "closed"
            t["closed_at"] = datetime.now(timezone.utc).isoformat()
            t["exit"] = t["sl"]
            t["result_r"] = r
            t["outcome"] = outcome
            closed_log.append(t)
            events.append(outcome)
            if record_closed_trade:
                try:
                    record_closed_trade(t)
                except Exception as e:
                    print("closed writer", e)
            continue

        if hit_tp1:
            t["tp1_hit"] = True
            t["be"] = True
            t["sl"] = t["entry"]  # move to BE
            msg = (
                f"🎯 TP1 HIT · {pair} {d}\n"
                f"Price ~{price}\n"
                f"Move SL → BE ({t['entry']})\n"
                f"Leave runner for TP2/TP3"
            )
            send_message(msg)
            events.append("TP1")
            if record_trade_update:
                try:
                    record_trade_update(t, "TP1")
                except Exception:
                    pass

        if hit_tp2:
            t["tp2_hit"] = True
            msg = (
                f"🎯 TP2 HIT · {pair} {d}\n"
                f"Price ~{price}\n"
                f"Partial done · runner → TP3"
            )
            send_message(msg)
            events.append("TP2")

        if hit_tp3:
            t["tp3_hit"] = True
            r = _r_multiple(t, t["tp3"])
            msg = (
                f"🏆 TP3 HIT · {pair} {d}\n"
                f"Price ~{price}\n"
                f"Full target · ~{r}R"
            )
            send_message(msg)
            t["status"] = "closed"
            t["closed_at"] = datetime.now(timezone.utc).isoformat()
            t["exit"] = t["tp3"]
            t["result_r"] = r
            t["outcome"] = "TP3"
            closed_log.append(t)
            events.append("TP3")
            if record_closed_trade:
                try:
                    record_closed_trade(t)
                except Exception:
                    pass
            continue

        still_open.append(t)

    data["open_trades"] = still_open
    data["closed_trades"] = closed_log[-100:]
    _save_raw(data)
    return events
