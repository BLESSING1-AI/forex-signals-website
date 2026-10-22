"""
Coinbase public candles — multi-product (PAXG-USD gold, BTC-USD, …)
Free, no API key. Max ~300 candles per request.
"""
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
from typing import Optional

from config import SYMBOLS

COINBASE_URL = "https://api.exchange.coinbase.com/products/{product_id}/candles"
MAX_BARS = 280

GRANULARITY = {
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "1d": 86400,
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
            headers={"User-Agent": "PriceActionEngine/1.0"},
        )
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        print(f"Coinbase error {product_id} {granularity}s: {e}")
        return []

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
    return df[["open", "high", "low", "close", "volume"]].astype(float).dropna()

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
    return data
