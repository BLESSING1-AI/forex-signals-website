"""Configuration"""
import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN",
    "8821872779:AAFIZW1pIaobz9MpQek5JoxXMWwAuX38_18",
)

# Numeric ID is required — @username fails with "chat not found" for channels
_raw_chat = os.getenv("TELEGRAM_CHANNEL_ID", "-1004499950812")
if _raw_chat and _raw_chat.lstrip("-").isdigit():
    TELEGRAM_CHANNEL_ID = _raw_chat
else:
    # Ignore bad secret like @PriceActionSignalsHub
    print(f"Ignoring non-numeric TELEGRAM_CHANNEL_ID={_raw_chat!r}, using numeric fallback")
    TELEGRAM_CHANNEL_ID = "-1004499950812"

MODE = "daily"
MAX_SIGNALS_PER_DAY = 4
MAX_MOMENTUM_PER_DAY = 5
PAIRS = ["XAUUSD"]
DEFAULT_RISK_PERCENT = 1.0
MOMENTUM_RISK_PERCENT = 0.5
XAU_SL_BUFFER = 25
LONDON_START, LONDON_END = 7, 16
NY_START, NY_END = 12, 21
MIN_RR_TP1 = 1.2
NEWS_BLACKOUT = False
