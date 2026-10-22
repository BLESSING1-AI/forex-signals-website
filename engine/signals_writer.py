"""Append posted setups into signals.json for the static website."""
import json
import os
from datetime import datetime, timezone
from typing import Dict, Any

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PATHS = [
    os.path.join(ROOT, "signals.json"),
    os.path.join(ROOT, "public", "signals.json"),
]
MAX_SIGNALS = 30
MAX_WATCH = 15

def _load(path: str) -> dict:
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print("signals_writer load", e)
    return {
        "lastUpdated": None,
        "mode": "scored",
        "pairs": ["XAUUSD", "BTCUSD"],
        "signals": [],
        "watchlist": [],
        "events": [],
    }

def _save(path: str, data: dict) -> None:
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print("signals_writer save", path, e)

def _row(setup: Dict[str, Any]) -> dict:
    return {
        "pair": setup.get("pair", "XAUUSD"),
        "direction": setup.get("direction"),
        "tier": setup.get("tier"),
        "score": setup.get("score"),
        "model": setup.get("model"),
        "entry_zone": setup.get("entry_zone"),
        "stop_loss": setup.get("stop_loss"),
        "tp1": setup.get("tp1"),
        "tp2": setup.get("tp2"),
        "tp3": setup.get("tp3"),
        "rr": setup.get("rr"),
        "reasons": setup.get("reasons") or [],
        "postedAt": datetime.now(timezone.utc).isoformat(),
    }

def record_signal(setup: Dict[str, Any], watchlist: bool = False) -> None:
    row = _row(setup)
    now = datetime.now(timezone.utc).isoformat()
    for path in PATHS:
        data = _load(path)
        data["lastUpdated"] = now
        data["pairs"] = ["XAUUSD", "BTCUSD"]
        data["mode"] = "scored"
        if watchlist:
            wl = data.get("watchlist") or []
            wl.insert(0, row)
            data["watchlist"] = wl[:MAX_WATCH]
        else:
            sigs = data.get("signals") or []
            sigs.insert(0, row)
            data["signals"] = sigs[:MAX_SIGNALS]
        _save(path, data)
    print("Website signals.json updated", "watchlist" if watchlist else "signal")
