"""Configuration — quality-first daily + momentum"""
import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN",
    "8821872779:AAFIZW1pIaobz9MpQek5JoxXMWwAuX38_18",
)

_raw_chat = os.getenv("TELEGRAM_CHANNEL_ID", "-1004499950812")
if _raw_chat and _raw_chat.lstrip("-").isdigit():
    TELEGRAM_CHANNEL_ID = _raw_chat
else:
    print(f"Ignoring non-numeric TELEGRAM_CHANNEL_ID={_raw_chat!r}")
    TELEGRAM_CHANNEL_ID = "-1004499950812"

MODE = "quality"
MAX_SIGNALS_PER_DAY = 3          # fewer, better daily PA
MAX_MOMENTUM_PER_DAY = 3         # only serious momentum
PAIRS = ["XAUUSD"]
DEFAULT_RISK_PERCENT = 1.0
MOMENTUM_RISK_PERCENT = 0.75
XAU_SL_BUFFER = 20
LONDON_START, LONDON_END = 7, 16
NY_START, NY_END = 12, 21
MIN_RR_TP1 = 1.5
NEWS_BLACKOUT = False
