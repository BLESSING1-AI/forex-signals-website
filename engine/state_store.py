"""Persist sent keys + daily signal count across Action runs."""
import json
import os
from datetime import datetime, timezone
from typing import Set, Dict, Any

STATE_PATH = os.path.join(os.path.dirname(__file__), ".signal_state.json")
MAX_KEYS = 200

def _load_raw() -> Dict[str, Any]:
    try:
        if not os.path.exists(STATE_PATH):
            return {"keys": [], "daily": {}}
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "keys" not in data:
            data["keys"] = []
        if "daily" not in data:
            data["daily"] = {}
        return data
    except Exception as e:
        print("state load error:", e)
        return {"keys": [], "daily": {}}

def load_sent() -> Set[str]:
    return set(_load_raw().get("keys", []))

def save_sent(keys: Set[str]) -> None:
    data = _load_raw()
    lst = list(keys)
    if len(lst) > MAX_KEYS:
        lst = lst[-MAX_KEYS:]
    data["keys"] = lst
    data["updated"] = datetime.now(timezone.utc).isoformat()
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception as e:
        print("state save error:", e)

def signals_posted_today() -> int:
    """How many trade signals already posted today (UTC date)."""
    data = _load_raw()
    today = datetime.now(timezone.utc).date().isoformat()
    d = data.get("daily") or {}
    if d.get("date") != today:
        return 0
    return int(d.get("count", 0))

def mark_signal_posted() -> int:
    data = _load_raw()
    today = datetime.now(timezone.utc).date().isoformat()
    d = data.get("daily") or {}
    if d.get("date") != today:
        d = {"date": today, "count": 0}
    d["count"] = int(d.get("count", 0)) + 1
    data["daily"] = d
    data["updated"] = datetime.now(timezone.utc).isoformat()
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception as e:
        print("state save error:", e)
    return d["count"]
