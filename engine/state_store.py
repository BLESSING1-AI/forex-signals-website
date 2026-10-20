"""Persist sent-signal keys across GitHub Action runs."""
import json
import os
from datetime import datetime, timezone
from typing import Set

STATE_PATH = os.path.join(os.path.dirname(__file__), ".signal_state.json")
MAX_KEYS = 200

def load_sent() -> Set[str]:
    try:
        if not os.path.exists(STATE_PATH):
            return set()
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        keys = data.get("keys", [])
        return set(keys)
    except Exception as e:
        print("state load error:", e)
        return set()

def save_sent(keys: Set[str]) -> None:
    try:
        # keep newest-ish by simple trim
        lst = list(keys)
        if len(lst) > MAX_KEYS:
            lst = lst[-MAX_KEYS:]
        payload = {
            "updated": datetime.now(timezone.utc).isoformat(),
            "keys": lst,
        }
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f)
    except Exception as e:
        print("state save error:", e)
