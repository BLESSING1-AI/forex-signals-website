"""
High-impact economic calendar
Uses free keyless API: biquote.io
Focus on USD high-impact events that move gold & FX
"""

import requests
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional

CALENDAR_URL = "https://biquote.io/api/calendar"

# Keywords that almost always move gold / USD pairs hard
HIGH_IMPACT_KEYWORDS = [
    "non-farm", "nonfarm", "nfp", "payroll",
    "cpi", "consumer price", "inflation",
    "fomc", "fed", "federal funds", "interest rate decision",
    "powell", "rate decision", "fomc minutes",
    "ppi", "producer price",
    "retail sales",
    "gdp",
    "unemployment",
    "ism", "pmi",
    "core pce", "pce",
    "jobless claims",
]

def _is_high_impact_name(name: str) -> bool:
    n = name.lower()
    return any(k in n for k in HIGH_IMPACT_KEYWORDS)

def fetch_upcoming_events(hours_ahead: int = 72) -> List[Dict]:
    """
    Fetch high-impact events for the next N hours (default 3 days).
    Returns list of event dicts sorted by time.
    """
    now = datetime.now(timezone.utc)
    end = now + timedelta(hours=hours_ahead)

    params = {
        "importance": "high",
        "countries": "US",
        "from": now.strftime("%Y-%m-%d"),
        "to": end.strftime("%Y-%m-%d"),
    }

    try:
        r = requests.get(CALENDAR_URL, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"Calendar fetch error: {e}")
        return []

    if not isinstance(data, list):
        data = data.get("events", data.get("data", []))

    events = []
    for e in data:
        name = e.get("name") or e.get("title") or e.get("event") or ""
        country = (e.get("countryCode") or e.get("country") or e.get("currency") or "").upper()
        importance = (e.get("importance") or "").lower()

        if country not in ("US", "USD") and "USD" not in country:
            # still allow if name is clearly major USD event
            if not _is_high_impact_name(name):
                continue

        if importance and importance not in ("high", "3", "red"):
            if not _is_high_impact_name(name):
                continue

        if not _is_high_impact_name(name) and importance != "high":
            continue

        time_str = e.get("time") or e.get("date") or e.get("datetime")
        try:
            if isinstance(time_str, (int, float)):
                etime = datetime.fromtimestamp(time_str, tz=timezone.utc)
            else:
                etime = datetime.fromisoformat(str(time_str).replace("Z", "+00:00"))
                if etime.tzinfo is None:
                    etime = etime.replace(tzinfo=timezone.utc)
        except Exception:
            continue

        if etime < now - timedelta(hours=1):
            continue
        if etime > end:
            continue

        events.append({
            "name": name.strip(),
            "time": etime,
            "country": "US",
            "currency": "USD",
            "forecast": e.get("forecast"),
            "previous": e.get("previous"),
            "actual": e.get("actual"),
            "importance": "high",
            "raw": e,
        })

    events.sort(key=lambda x: x["time"])
    return events

def get_events_in_window(minutes_before: int = 90, minutes_after: int = 30) -> List[Dict]:
    """
    Events that are about to happen or just happened (for pre/post logic).
    """
    now = datetime.now(timezone.utc)
    all_events = fetch_upcoming_events(hours_ahead=48)

    window = []
    for e in all_events:
        delta = (e["time"] - now).total_seconds() / 60
        if -minutes_after <= delta <= minutes_before:
            e["minutes_to_event"] = delta
            window.append(e)
    return window
