"""Configuration - Strict Mode XAUUSD"""
import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8821872779:AAFIZW1pIaobz9MpQek5JoxXMWwAuX38_18")
# Numeric channel ID is more reliable than @username
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "-1004499950812")

MODE = "strict"
MAX_SIGNALS_PER_DAY = 2
PAIRS = ["XAUUSD"]
DEFAULT_RISK_PERCENT = 1.0
XAU_SL_BUFFER = 25
LONDON_START, LONDON_END = 7, 16
NY_START, NY_END = 12, 21
MIN_RR_TP1 = 1.5
NEWS_BLACKOUT = False
