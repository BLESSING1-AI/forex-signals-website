"""Persist sent keys, daily counts, cooldowns, fingerprints."""
import json
import os
from datetime import datetime, timezone, timedelta
from typing import Set, Dict, Any, Optional

STATE_PATH = os.path.join(os.path.dirname(__file__), ".signal_state.json")
MAX_KEYS = 300

def _load_raw() -> Dict[str, Any]:
    try:
        if not os.path.exists(STATE_PATH):
            return {"keys": [], "daily": {}, "cooldown": {}, "fingerprints": {}}
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k, default in [("keys", []), ("daily", {}), ("cooldown", {}), ("fingerprints", {})]:
            if k not in data:
                data[k] = default
        return data
    except Exception as e:
        print("state load error:", e)
        return {"keys": [], "daily": {}, "cooldown": {}, "fingerprints": {}}

def _save_raw(data: Dict[str, Any]) -> None:
    data["updated"] = datetime.now(timezone.utc).isoformat()
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception as e:
        print("state save error:", e)

def load_sent() -> Set[str]:
    return set(_load_raw().get("keys", []))

def save_sent(keys: Set[str]) -> None:
    data = _load_raw()
    lst = list(keys)
    if len(lst) > MAX_KEYS:
        lst = lst[-MAX_KEYS:]
    data["keys"] = lst
    _save_raw(data)

def signals_posted_today(symbol: str = "XAUUSD") -> int:
    data = _load_raw()
    today = datetime.now(timezone.utc).date().isoformat()
    d = data.get("daily") or {}
    if d.get("date") != today:
        return 0
    return int(d.get(symbol, d.get("count", 0)))

def mark_signal_posted(symbol: str = "XAUUSD") -> int:
    data = _load_raw()
    today = datetime.now(timezone.utc).date().isoformat()
    d = data.get("daily") or {}
    if d.get("date") != today:
        d = {"date": today}
    d[symbol] = int(d.get(symbol, 0)) + 1
    d["count"] = int(d.get("count", 0)) + 1
    data["daily"] = d
    _save_raw(data)
    return d[symbol]

def cooldown_ok(symbol: str, minutes: int) -> bool:
    data = _load_raw()
    cd = data.get("cooldown") or {}
    last = cd.get(symbol)
    if not last:
        return True
    try:
        t = datetime.fromisoformat(last)
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - t >= timedelta(minutes=minutes)
    except Exception:
        return True

def mark_cooldown(symbol: str) -> None:
    data = _load_raw()
    cd = data.get("cooldown") or {}
    cd[symbol] = datetime.now(timezone.utc).isoformat()
    data["cooldown"] = cd
    _save_raw(data)

def fingerprint(setup: Dict[str, Any]) -> str:
    zone = str(setup.get("entry_zone", ""))
    # bucket zone to avoid tiny float differences
    try:
        parts = zone.split("-")
        a = round(float(parts[0]) / 5) * 5
        b = round(float(parts[1]) / 5) * 5
        zone_b = f"{a}-{b}"
    except Exception:
        zone_b = zone
    return "|".join(
        [
            str(setup.get("pair", "XAUUSD")),
            str(setup.get("direction", "")),
            zone_b,
            str(setup.get("model", "")),
            str(setup.get("structure_level", "")),
        ]
    )

def is_duplicate(setup: Dict[str, Any], hours: int = 6) -> bool:
    fp = fingerprint(setup)
    data = _load_raw()
    fps = data.get("fingerprints") or {}
    last = fps.get(fp)
    if not last:
        return False
    try:
        t = datetime.fromisoformat(last)
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - t < timedelta(hours=hours)
    except Exception:
        return False

def mark_fingerprint(setup: Dict[str, Any]) -> None:
    fp = fingerprint(setup)
    data = _load_raw()
    fps = data.get("fingerprints") or {}
    fps[fp] = datetime.now(timezone.utc).isoformat()
    # prune old
    if len(fps) > 100:
        items = sorted(fps.items(), key=lambda x: x[1])[-80:]
        fps = dict(items)
    data["fingerprints"] = fps
    _save_raw(data)
