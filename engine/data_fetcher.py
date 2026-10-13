"""
Data fetching module for XAUUSD
Uses yfinance as free starting source (delayed).
Can be swapped later for higher quality paid feeds.
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta


def fetch_ohlc(symbol: str = "GC=F", interval: str = "15m", period: str = "5d") -> pd.DataFrame:
    """
    Fetch OHLC data.

    Note: yfinance uses GC=F for Gold futures as a proxy for XAUUSD.
    For production, replace with a proper XAUUSD feed (Twelve Data, Polygon, broker API, etc.)
    """
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval)

        if df.empty:
            print(f"No data returned for {symbol} {interval}")
            return pd.DataFrame()

        df = df.rename(columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume"
        })

        df = df[["open", "high", "low", "close", "volume"]].dropna()
        df.index = pd.to_datetime(df.index)

        return df

    except Exception as e:
        print(f"Error fetching data: {e}")
        return pd.DataFrame()


def get_multi_timeframe_data():
    """
    Returns a dictionary of dataframes for the required timeframes
    """
    data = {}

    # Daily
    data["1d"] = fetch_ohlc(interval="1d", period="6mo")

    # 4-hour (approximate with 60m and resample if needed)
    h1 = fetch_ohlc(interval="60m", period="60d")
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
    data["15m"] = fetch_ohlc(interval="15m", period="10d")

    # 5-minute
    data["5m"] = fetch_ohlc(interval="5m", period="5d")

    return data
