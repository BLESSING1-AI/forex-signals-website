"""
Data fetching module for Gold (XAUUSD proxy)
Uses Coinbase public Advanced Trade / Exchange candles endpoint (free, no API key).
Product: PAXG-USD (PAX Gold) – tracks physical gold price closely.
"""

import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
from typing import Optional

# Coinbase public endpoints (no auth required)
COINBASE_CANDLES_URL = "https://api.exchange.coinbase.com/products/{product_id}/candles"
PRODUCT_ID = "PAXG-USD"   # PAX Gold – best free gold proxy on Coinbase

# Granularity in seconds (Coinbase allowed values)
GRANULARITY = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "6h": 21600,
    "1d": 86400,
}


def _fetch_candles(product_id: str, granularity: int, start: datetime, end: datetime) -> list:
    """
    Fetch up to 300 candles from Coinbase.
    """
    params = {
        "granularity": granularity,
        "start": start.isoformat(),
        "end": end.isoformat(),
    }
    try:
        resp = requests.get(
            COINBASE_CANDLES_URL.format(product_id=product_id),
            params=params,
            timeout=15
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"Coinbase fetch error: {e}")
        return []


def fetch_ohlc(
    interval: str = "15m",
    days: int = 5,
    product_id: str = PRODUCT_ID
) -> pd.DataFrame:
    """
    Fetch OHLC data from Coinbase and return a clean DataFrame.

    interval: one of '1m', '5m', '15m', '1h', '6h', '1d'
    days: how many days of history to request
    """
    if interval not in GRANULARITY:
        print(f"Unsupported interval: {interval}")
        return pd.DataFrame()

    gran = GRANULARITY[interval]
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    raw = _fetch_candles(product_id, gran, start, end)

    if not raw:
        return pd.DataFrame()

    # Coinbase returns: [time, low, high, open, close, volume]
    df = pd.DataFrame(raw, columns=["time", "low", "high", "open", "close", "volume"])
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df = df.set_index("time").sort_index()
    df = df[["open", "high", "low", "close", "volume"]].astype(float)

    return df.dropna()


def get_multi_timeframe_data() -> dict:
    """
    Returns a dictionary of DataFrames for the required timeframes.
    We approximate 4H by resampling 1H data.
    """
    data = {}

    # Daily
    data["1d"] = fetch_ohlc(interval="1d", days=180)

    # 1-hour (used for 4H resampling)
    h1 = fetch_ohlc(interval="1h", days=60)
    data["1h"] = h1

    if not h1.empty:
        data["4h"] = h1.resample("4h").agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum"
        }).dropna()
    else:
        data["4h"] = pd.DataFrame()

    # 15-minute
    data["15m"] = fetch_ohlc(interval="15m", days=10)

    # 5-minute
    data["5m"] = fetch_ohlc(interval="5m", days=5)

    return data


if __name__ == "__main__":
    # Quick test
    print("Testing Coinbase PAXG-USD data...")
    df = fetch_ohlc("15m", days=2)
    print(df.tail() if not df.empty else "No data returned")
    print("\nMulti-timeframe:")
    mtf = get_multi_timeframe_data()
    for tf, d in mtf.items():
        print(f"  {tf}: {len(d)} bars")
