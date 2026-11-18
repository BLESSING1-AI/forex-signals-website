"""Persist sent keys, daily counts, cooldowns, fingerprints, open trades.
Atomic writes + basic schema validation.
"""
import json
import os
import tempfile
from datetime import datetime, timezone, timedelta
from typing import Set, Dict, Any, Optional

STATE_PATH = os.path.join(os.path.dirname(__file__), ".signal_state.json")
STATE_VERSION = 2
MAX_KEYS = 300


def _default() -> Dict[str, Any]:
    return {
        "version": STATE_VERSION,
        "keys": [],
        "daily": {},
        "cooldown": {},
        "fingerprints": {},
        "open_trades": [],
        "closed_trades": [],
    }


def _validate(data: Any) -> Dict[str, Any]:
    if not isinstance(data, dict):
        return _default()
    out = _default()
    out["keys"] = list(data.get("keys") or [])[-MAX_KEYS:]
    out["daily"] = data.get("daily") if isinstance(data.get("daily"), dict) else {}
    out["cooldown"] = data.get("cooldown") if isinstance(data.get("cooldown"), dict) else {}
    out["fingerprints"] = (
        data.get("fingerprints") if isinstance(data.get("fingerprints"), dict) else {}
    )
    out["open_trades"] = (
        data.get("open_trades") if isinstance(data.get("open_trades"), list) else []
    )
    out["closed_trades"] = (
        data.get("closed_trades") if isinstance(data.get("closed_trades"), list) else []
    )
    out["version"] = STATE_VERSION
    if data.get("updated"):
        out["updated"] = data["updated"]
    return out


def _load_raw() -> Dict[str, Any]:
    try:
        if not os.path.exists(STATE_PATH):
            return _default()
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return _validate(data)
    except Exception as e:
        print("state load error — recovering defaults:", e)
        return _default()


def _save_raw(data: Dict[str, Any]) -> None:
    data = _validate(data)
    data["updated"] = datetime.now(timezone.utc).isoformat()
    data["version"] = STATE_VERSION
    try:
        directory = os.path.dirname(STATE_PATH) or "."
        fd, tmp = tempfile.mkstemp(prefix=".state_", suffix=".json", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, STATE_PATH)
        except Exception:
            try:
                os.unlink(tmp)
            except Exception:
                pass
            raise
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
    if len(fps) > 100:
        items = sorted(fps.items(), key=lambda x: x[1])[-80:]
        fps = dict(items)
    data["fingerprints"] = fps
    _save_raw(data)
