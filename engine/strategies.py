"""
Strategy labels and per-strategy thresholds.
Actual detection remains in scoring/structure; this maps model → strategy metadata.
"""
from typing import Dict, Any

STRATEGY_META: Dict[str, Dict[str, Any]] = {
    "gold_pullback": {"pair": "XAUUSD", "min_score": 72, "style": "pullback"},
    "fvg_pullback": {"pair": "BOTH", "min_score": 70, "style": "pullback"},
    "sweep": {"pair": "BOTH", "min_score": 72, "style": "reversal"},
    "liquidity_reversal": {"pair": "BOTH", "min_score": 74, "style": "reversal"},
    "momentum_breakout": {"pair": "BTCUSD", "min_score": 68, "style": "breakout"},
    "breakout": {"pair": "BTCUSD", "min_score": 68, "style": "breakout"},
    "continuation": {"pair": "BOTH", "min_score": 70, "style": "trend"},
    "trend_continuation": {"pair": "BOTH", "min_score": 70, "style": "trend"},
    "day_trade": {"pair": "BOTH", "min_score": 70, "style": "intraday"},
    "pullback": {"pair": "BOTH", "min_score": 70, "style": "pullback"},
}


def strategy_min_score(model: str, default: int = 70) -> int:
    meta = STRATEGY_META.get(model or "", {})
    return int(meta.get("min_score", default))


def strategy_style(model: str) -> str:
    return str(STRATEGY_META.get(model or "", {}).get("style", "price_action"))
