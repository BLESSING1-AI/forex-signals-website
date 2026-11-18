"""
Coinbase public candles — multi-product (PAXG-USD gold proxy, BTC-USD).
Free, no API key. Max ~300 candles per request.
Includes freshness + OHLC integrity checks.
Note: PAXG is not identical to broker XAUUSD.
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

# Max age of last candle before considering data stale (seconds)
STALE_THRESHOLDS = {
    "5m": 15 * 60,
    "15m": 40 * 60,
    "1h": 3 * 3600,
    "1d": 36 * 3600,
}


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
            headers={"User-Agent": "PriceActionEngine/1.1"},
        )
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        print(f"Coinbase error {product_id} {granularity}s: {e}")
        return []


def _validate_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows with invalid OHLC relationships or extreme spikes."""
    if df is None or df.empty:
        return df
    out = df.copy()
    # Basic integrity
    mask = (
        (out["high"] >= out["low"])
        & (out["high"] >= out["open"])
        & (out["high"] >= out["close"])
        & (out["low"] <= out["open"])
        & (out["low"] <= out["close"])
        & (out["open"] > 0)
        & (out["close"] > 0)
    )
    dropped = int((~mask).sum())
    if dropped:
        print(f"OHLC integrity: dropped {dropped} bad bars")
    out = out[mask]
    # Deduplicate index
    out = out[~out.index.duplicated(keep="last")]
    return out.sort_index()


def _freshness(df: pd.DataFrame, interval: str) -> Dict[str, Any]:
    if df is None or df.empty:
        return {"status": "empty", "age_sec": None}
    last_ts = df.index[-1]
    if last_ts.tzinfo is None:
        last_ts = last_ts.replace(tzinfo=timezone.utc)
    age = (datetime.now(timezone.utc) - last_ts).total_seconds()
    thresh = STALE_THRESHOLDS.get(interval, 3600)
    status = "ok" if age <= thresh else "stale"
    return {"status": status, "age_sec": round(age), "last_bar": last_ts.isoformat()}


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
    df = df[["open", "high", "low", "close", "volume"]].astype(float).dropna()
    return _validate_ohlc(df)


def get_multi_timeframe_data(symbol: str = "XAUUSD") -> dict:
    data: Dict[str, Any] = {}
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

    # Aggregate quality from primary TFs
    qualities = []
    for k in ("15m", "1h", "5m"):
        q = _freshness(data.get(k), k)
        qualities.append(q)
        print(f"{symbol} TF {k}: {0 if data[k] is None or data[k].empty else len(data[k])} bars age={q.get('age_sec')}s [{q.get('status')}]")

    if any(q.get("status") == "stale" for q in qualities if q.get("status") != "empty"):
        data["_quality"] = {"status": "stale", "details": qualities}
    elif all(q.get("status") == "empty" for q in qualities):
        data["_quality"] = {"status": "empty", "details": qualities}
    else:
        data["_quality"] = {"status": "ok", "details": qualities}

    # Explicit proxy note for gold consumers
    if symbol == "XAUUSD":
        data["_proxy_note"] = "PAXG-USD is a Coinbase gold proxy; not identical to broker XAUUSD"

    return data
