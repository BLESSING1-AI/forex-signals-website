"""
Gemini AI verification layer.
AI evaluates setups only — never invents entry/SL/TP.
Deterministic engine owns all prices and hard risk rules.
"""
from __future__ import annotations
import json
import os
import time
import hashlib
from typing import Any, Dict, Optional, Tuple

import requests

from config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GEMINI_TIMEOUT_SEC,
    GEMINI_MAX_RETRIES,
    AI_ENABLED,
    AI_CACHE_TTL_SEC,
)

_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
VALID_DECISIONS = {"APPROVE", "REJECT", "WATCH"}


def _empty(decision: str, reason: str, confidence: int = 0) -> Dict[str, Any]:
    return {
        "decision": decision,
        "confidence": confidence,
        "direction": None,
        "setup_quality": None,
        "confirmations": [],
        "warnings": [reason],
        "rejection_reasons": [reason] if decision == "REJECT" else [],
        "explanation": reason,
        "ai_status": "unavailable",
        "model": GEMINI_MODEL,
    }


def _cache_key(setup: Dict[str, Any], regime: Dict[str, Any]) -> str:
    raw = json.dumps(
        {
            "pair": setup.get("pair"),
            "direction": setup.get("direction"),
            "score": setup.get("score"),
            "model": setup.get("model"),
            "entry": setup.get("entry_zone"),
            "sl": setup.get("stop_loss"),
            "tp1": setup.get("tp1"),
            "reasons": setup.get("reasons"),
            "regime": regime.get("regime"),
            "htf": setup.get("htf"),
        },
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _parse_json_loose(text: str) -> Optional[Dict[str, Any]]:
    text = (text or "").strip()
    if not text:
        return None
    if "```" in text:
        parts = text.split("```")
        for p in parts:
            p = p.strip()
            if p.startswith("json"):
                p = p[4:].strip()
            if p.startswith("{"):
                text = p
                break
    try:
        return json.loads(text)
    except Exception:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except Exception:
                return None
    return None


def _validate(obj: Any, setup: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(obj, dict):
        return None
    decision = str(obj.get("decision", "")).upper().strip()
    if decision not in VALID_DECISIONS:
        return None
    try:
        confidence = int(obj.get("confidence", 0))
    except Exception:
        return None
    confidence = max(0, min(100, confidence))

    direction = obj.get("direction")
    if direction is not None:
        direction = str(direction).upper()
        if direction not in ("BUY", "SELL", "NEUTRAL"):
            direction = setup.get("direction")

    confs = obj.get("confirmations") or []
    warns = obj.get("warnings") or []
    rejects = obj.get("rejection_reasons") or []
    if not isinstance(confs, list):
        confs = [str(confs)]
    if not isinstance(warns, list):
        warns = [str(warns)]
    if not isinstance(rejects, list):
        rejects = [str(rejects)]

    return {
        "decision": decision,
        "confidence": confidence,
        "direction": direction or setup.get("direction"),
        "setup_quality": obj.get("setup_quality"),
        "confirmations": [str(x) for x in confs][:8],
        "warnings": [str(x) for x in warns][:8],
        "rejection_reasons": [str(x) for x in rejects][:8],
        "explanation": str(obj.get("explanation") or "")[:600],
        "ai_status": "ok",
        "model": GEMINI_MODEL,
    }


def _build_prompt(setup: Dict[str, Any], regime: Dict[str, Any]) -> str:
    return f"""You are a strict price-action trading reviewer for XAUUSD and BTCUSD.
You do NOT invent entry, stop-loss, or take-profit prices. Levels below were calculated by a deterministic engine and are fixed.

SETUP (fixed levels — do not change):
{json.dumps({k: setup.get(k) for k in [
    "pair","direction","score","tier","model","reasons","entry_zone",
    "stop_loss","tp1","tp2","tp3","rr","htf","h1","confirmations","struct_pts","momentum_pts"
]}, default=str)}

MARKET REGIME:
{json.dumps(regime, default=str)}

Evaluate independently:
- Direction validity vs HTF
- BOS/CHoCH/liquidity sweep/FVG quality if claimed
- Late entry or exhaustion risk
- Liquidity traps / fakeouts
- Regime fit for this strategy
- Conflicting signals

Respond with ONLY valid JSON (no markdown) matching:
{{
  "decision": "APPROVE" | "REJECT" | "WATCH",
  "confidence": 0-100,
  "direction": "BUY" | "SELL" | "NEUTRAL",
  "setup_quality": "A+" | "A" | "B" | "C" | "F",
  "confirmations": ["..."],
  "warnings": ["..."],
  "rejection_reasons": ["..."],
  "explanation": "short reason"
}}

Rules:
- REJECT if late, exhausted, trap, or HTF conflict is severe.
- WATCH if developing but not ready.
- APPROVE only if quality is genuinely tradeable.
- Never output new price levels.
"""


def verify_setup(
    setup: Dict[str, Any],
    regime: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    regime = regime or {}
    if not AI_ENABLED:
        return _empty("WATCH", "AI disabled", 0)

    if not GEMINI_API_KEY:
        return _empty("REJECT", "GEMINI_API_KEY missing — not AI-approved", 0)

    key = _cache_key(setup, regime)
    now = time.time()
    if key in _CACHE:
        ts, cached = _CACHE[key]
        if now - ts < AI_CACHE_TTL_SEC:
            out = dict(cached)
            out["ai_status"] = "cached"
            return out

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )
    body = {
        "contents": [{"role": "user", "parts": [{"text": _build_prompt(setup, regime)}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 512,
            "responseMimeType": "application/json",
        },
    }

    last_err = "unknown"
    for attempt in range(max(1, GEMINI_MAX_RETRIES)):
        try:
            r = requests.post(url, json=body, timeout=GEMINI_TIMEOUT_SEC)
            if r.status_code == 429:
                last_err = "quota/rate limit"
                time.sleep(1.5 * (attempt + 1))
                continue
            if r.status_code >= 400:
                last_err = f"http {r.status_code}"
                time.sleep(0.5)
                continue
            data = r.json()
            text = ""
            for cand in data.get("candidates") or []:
                parts = ((cand.get("content") or {}).get("parts")) or []
                for p in parts:
                    text += p.get("text") or ""
            parsed = _parse_json_loose(text)
            validated = _validate(parsed, setup)
            if not validated:
                last_err = "invalid JSON schema"
                continue
            eng_dir = str(setup.get("direction", "")).upper()
            if (
                validated["decision"] == "APPROVE"
                and validated.get("direction") in ("BUY", "SELL")
                and eng_dir in ("BUY", "SELL")
                and validated["direction"] != eng_dir
            ):
                validated["decision"] = "REJECT"
                validated["rejection_reasons"].append("AI direction conflicts with engine")
                validated["explanation"] = "Rejected: AI direction mismatch with deterministic engine"
            _CACHE[key] = (now, validated)
            return validated
        except requests.Timeout:
            last_err = "timeout"
        except Exception as e:
            last_err = str(e)[:120]
            time.sleep(0.4)

    return _empty("REJECT", f"AI verification failed ({last_err}) — not approved", 0)


def apply_ai_gate(
    setup: Dict[str, Any],
    ai: Dict[str, Any],
    strict: bool,
) -> Dict[str, Any]:
    out = dict(setup)
    out["ai"] = ai
    decision = (ai or {}).get("decision", "REJECT")
    status = (ai or {}).get("ai_status", "unavailable")

    if decision == "APPROVE" and status in ("ok", "cached"):
        out["action"] = "signal"
        if out.get("tier") == "WATCHLIST":
            out["tier"] = "A"
        return out

    if decision == "WATCH":
        out["action"] = "watchlist"
        out["tier"] = "WATCHLIST"
        return out

    if strict or status not in ("ok", "cached"):
        out["action"] = "reject"
        out["tier"] = "REJECT"
        return out

    out["action"] = "watchlist"
    out["tier"] = "WATCHLIST"
    return out
