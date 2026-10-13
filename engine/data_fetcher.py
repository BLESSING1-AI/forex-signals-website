"""
Coinbase public candles for PAXG-USD (gold proxy)
Free, no API key required.
"""
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone

COINBASE_URL = "https://api.exchange.coinbase.com/products/{product_id}/candles"
PRODUCT_ID = "PAXG-USD"

GRANULARITY = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "6h": 21600,
    "1d": 86400,
}

def _fetch(product_id: str, granularity: int, start: datetime, end: datetime) -> list:
    params = {
        "granularity": granularity,
        "start": start.isoformat(),
        "end": end.isoformat(),
    }
    try:
        r = requests.get(COINBASE_URL.format(product_id=product_id), params=params, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"Coinbase error: {e}")
        return []

def fetch_ohlc(interval: str = "15m", days: int = 5) -> pd.DataFrame:
    if interval not in GRANULARITY:
        return pd.DataFrame()
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    raw = _fetch(PRODUCT_ID, GRANULARITY[interval], start, end)
    if not raw:
        return pd.DataFrame()
    # [time, low, high, open, close, volume]
    df = pd.DataFrame(raw, columns=["time", "low", "high", "open", "close", "volume"])
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df = df.set_index("time").sort_index()
    return df[["open", "high", "low", "close", "volume"]].astype(float).dropna()

def get_multi_timeframe_data() -> dict:
    data = {}
    data["1d"] = fetch_ohlc("1d", days=180)
    h1 = fetch_ohlc("1h", days=60)
    data["1h"] = h1
    if not h1.empty:
        data["4h"] = h1.resample("4h").agg({
            "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"
        }).dropna()
    else:
        data["4h"] = pd.DataFrame()
    data["15m"] = fetch_ohlc("15m", days=10)
    data["5m"] = fetch_ohlc("5m", days=5)
    return data
