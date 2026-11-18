"""
Coinbase public candles — multi-product (PAXG-USD gold proxy, BTC-USD).
PAXG is NOT identical to broker XAUUSD — levels can differ slightly.
Designed so additional data providers can be added later.
"""
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

from config import SYMBOLS

COINBASE_URL = "https://api.exchange.coinbase.com/products/{product_id}/candles"
MAX_BARS = 280

GRANULARITY = {
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "1d": 86400,
}

# Stale if last candle older than this many seconds for TF
STALE_SEC = {"5m": 900, "15m": 2400, "1h": 9000, "1d": 200000}


def product_for(symbol: str) -> str:
    meta = SYMBOLS.get(symbol) or SYMBOLS.get("XAUUSD")
    return meta["product"]


def _fetch(product_id: str, granularity: int, start: datetime, end: datetime) -> list:
    params = {
        "granularity": granularity,
        "start": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    try:
        r = requests.get(
            COINBASE_URL.format(product_id=product_id),
            params=params,
            timeout=20,
            headers={"User-Agent": "PriceActionEngine/1.0"},
        )
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        print(f"Coinbase error {product_id} {granularity}s: {e}")
        return []


def _sanitize(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    df = df[~df.index.duplicated(keep="last")].sort_index()
    for c in ("open", "high", "low", "close", "volume"):
        if c not in df.columns:
            return pd.DataFrame()
    df = df.astype(float)
    # OHLC integrity: high >= max(o,c), low <= min(o,c)
    bad = (
        (df["high"] < df[["open", "close"]].max(axis=1))
        | (df["low"] > df[["open", "close"]].min(axis=1))
        | (df["high"] < df["low"])
        | (df["close"] <= 0)
    )
    if bad.any():
        df = df.loc[~bad]
    # Drop extreme spikes (bad ticks) vs median close
    if len(df) >= 20:
        med = float(df["close"].tail(50).median() or 0)
        if med > 0:
            df = df[(df["close"] > med * 0.5) & (df["close"] < med * 1.5)]
    return df.dropna()


def fetch_ohlc(symbol: str = "XAUUSD", interval: str = "15m") -> pd.DataFrame:
    if interval not in GRANULARITY:
        return pd.DataFrame()

    product_id = product_for(symbol)
    gran = GRANULARITY[interval]
    end = datetime.now(timezone.utc)
    span = timedelta(seconds=gran * MAX_BARS)
    start = end - span

    raw = _fetch(product_id, gran, start, end)
    if not raw:
        return pd.DataFrame()

    df = pd.DataFrame(raw, columns=["time", "low", "high", "open", "close", "volume"])
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df = df.set_index("time").sort_index()
    df = _sanitize(df[["open", "high", "low", "close", "volume"]])

    if not df.empty:
        age = (datetime.now(timezone.utc) - df.index[-1].to_pydatetime()).total_seconds()
        limit = STALE_SEC.get(interval, 3600)
        if age > limit:
            print(f"WARN {symbol} {interval}: last candle age {int(age)}s (stale>{limit})")
    return df


def data_health(symbol: str, data: Dict[str, Any]) -> Dict[str, Any]:
    health = {"symbol": symbol, "ok": True, "notes": []}
    if symbol == "XAUUSD":
        health["notes"].append("PAXG-USD proxy — not broker XAUUSD")
    for tf in ("15m", "1h", "4h"):
        df = data.get(tf)
        n = 0 if df is None or getattr(df, "empty", True) else len(df)
        if n < 30:
            health["ok"] = False
            health["notes"].append(f"{tf} thin ({n} bars)")
    return health


def get_multi_timeframe_data(symbol: str = "XAUUSD") -> dict:
    data = {}
    data["1d"] = fetch_ohlc(symbol, "1d")
    h1 = fetch_ohlc(symbol, "1h")
    data["1h"] = h1
    if not h1.empty:
        data["4h"] = (
            h1.resample("4h")
            .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
            .dropna()
        )
    else:
        data["4h"] = pd.DataFrame()
    data["15m"] = fetch_ohlc(symbol, "15m")
    data["5m"] = fetch_ohlc(symbol, "5m")

    for k, v in data.items():
        n = 0 if v is None or v.empty else len(v)
        print(f"{symbol} TF {k}: {n} bars")

    h = data_health(symbol, data)
    if not h["ok"] or h["notes"]:
        print(f"data health {symbol}:", h)
    data["_health"] = h
    return data
