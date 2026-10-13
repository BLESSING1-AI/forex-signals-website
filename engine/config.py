"""
Configuration for Price Action Signals Engine
Strict Mode - XAUUSD only
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8821872779:AAFIZW1pIaobz9MpQek5JoxXMWwAuX38_18")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "@PriceActionSignalsHub")

# Mode
MODE = "strict"                    # strict = 1-2 signals max per day
MAX_SIGNALS_PER_DAY = 2
PAIRS = ["XAUUSD"]

# Risk
DEFAULT_RISK_PERCENT = 1.0

# Timeframes
HTF = ["1d", "4h"]                 # Higher timeframe for bias
LTF = ["15m", "5m"]                # Lower timeframe for confirmation

# Gold volatility buffer (pips)
XAU_SL_BUFFER = 25                 # extra pips added beyond structure for gold

# Session filters (UTC)
LONDON_START = 7                   # 07:00 UTC
LONDON_END = 16
NY_START = 12
NY_END = 21

# Quality filters
MIN_RR_TP1 = 1.5
MIN_RR_TP3 = 4.0

# News blackout (major events) - simple daily windows for now
# In production this should pull from an economic calendar API
NEWS_BLACKOUT = False              # set True during NFP/CPI/FOMC days
