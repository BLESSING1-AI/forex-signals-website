"""Lightweight indicators — EMA, RSI, ATR. No redundant overlap."""
from __future__ import annotations
from typing import Optional, Dict, Any
import pandas as pd
import numpy as np


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.astype(float).ewm(span=span, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    s = series.astype(float)
    delta = s.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    h = df["high"].astype(float)
    l = df["low"].astype(float)
    c = df["close"].astype(float)
    tr = pd.concat([(h - l), (h - c.shift(1)).abs(), (l - c.shift(1)).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def snapshot(df: pd.DataFrame) -> Dict[str, Any]:
    """Last-bar indicator snapshot for AI / regime context."""
    if df is None or df.empty or len(df) < 30:
        return {}
    close = df["close"].astype(float)
    out: Dict[str, Any] = {
        "price": float(close.iloc[-1]),
        "ema9": float(ema(close, 9).iloc[-1]),
        "ema21": float(ema(close, 21).iloc[-1]),
        "ema50": float(ema(close, 50).iloc[-1]) if len(df) >= 50 else None,
        "rsi14": float(rsi(close, 14).iloc[-1]) if len(df) >= 15 else None,
        "atr14": float(atr(df, 14).iloc[-1]) if len(df) >= 15 else None,
    }
    if len(df) >= 200:
        out["ema200"] = float(ema(close, 200).iloc[-1])
    vol = df["volume"].astype(float) if "volume" in df.columns else None
    if vol is not None and len(vol) >= 20:
        out["vol_ratio"] = float(vol.iloc[-1] / (vol.tail(20).mean() or 1))
    return out


def trend_from_emas(snap: Dict[str, Any]) -> str:
    p = snap.get("price")
    e9, e21 = snap.get("ema9"), snap.get("ema21")
    e50 = snap.get("ema50")
    if p is None or e9 is None or e21 is None:
        return "unknown"
    if e9 > e21 and (e50 is None or e21 > e50) and p > e9:
        return "bullish"
    if e9 < e21 and (e50 is None or e21 < e50) and p < e9:
        return "bearish"
    return "mixed"
