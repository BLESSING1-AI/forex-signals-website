"""
Trade lifecycle: closest TP first → BE, then mid/far TPs, SL, close.
TP labels on signals: TP1 furthest / TP3 closest — management uses distance order.
"""
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

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
        "tp1": float(setup.get("tp1", 0)),  # furthest
        "tp2": float(setup.get("tp2", 0)),
        "tp3": float(setup.get("tp3", 0)),  # closest
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


def _hit(direction: str, price: float, level: float) -> bool:
    if direction == "BUY":
        return price >= level
    return price <= level


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
        # SL / BE exit
        hit_sl = price <= t["sl"] if d == "BUY" else price >= t["sl"]
        if hit_sl:
            r = _r_multiple(t, t["sl"])
            outcome = "BE" if t.get("be") and abs(r) < 0.2 else "SL"
            msg = (
                f"{'✅ BE EXIT' if outcome == 'BE' else '❌ SL HIT'} · {pair} {d}\n"
                f"Price ~{round(price, 2)}\n"
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

        # Manage by proximity: TP3 (closest) → TP2 → TP1 (furthest)
        # Closest first → BE
        if not t.get("tp3_hit") and _hit(d, price, t["tp3"]):
            t["tp3_hit"] = True
            t["be"] = True
            t["sl"] = t["entry"]
            msg = (
                f"🎯 TP3 (closest) HIT · {pair} {d}\n"
                f"Price ~{round(price, 2)}\n"
                f"Move SL → BE ({round(t['entry'], 2)})\n"
                f"Runner on for TP2 / TP1"
            )
            send_message(msg)
            events.append("TP3")
            if record_trade_update:
                try:
                    record_trade_update(t, "TP3")
                except Exception:
                    pass

        if not t.get("tp2_hit") and _hit(d, price, t["tp2"]):
            t["tp2_hit"] = True
            if not t.get("be"):
                t["be"] = True
                t["sl"] = t["entry"]
            msg = (
                f"🎯 TP2 HIT · {pair} {d}\n"
                f"Price ~{round(price, 2)}\n"
                f"Partial · runner → TP1 (final)"
            )
            send_message(msg)
            events.append("TP2")

        if not t.get("tp1_hit") and _hit(d, price, t["tp1"]):
            t["tp1_hit"] = True
            r = _r_multiple(t, t["tp1"])
            msg = (
                f"🏆 TP1 (final) HIT · {pair} {d}\n"
                f"Price ~{round(price, 2)}\n"
                f"Full scale-out · ~{r}R"
            )
            send_message(msg)
            t["status"] = "closed"
            t["closed_at"] = datetime.now(timezone.utc).isoformat()
            t["exit"] = t["tp1"]
            t["result_r"] = r
            t["outcome"] = "TP1"
            closed_log.append(t)
            events.append("TP1")
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
