"""Configuration — scored quality system + separate news engine"""
import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN",
    "8821872779:AAFIZW1pIaobz9MpQek5JoxXMWwAuX38_18",
)

_raw_chat = os.getenv("TELEGRAM_CHANNEL_ID", "-1004499950812")
if _raw_chat and str(_raw_chat).lstrip("-").isdigit():
    TELEGRAM_CHANNEL_ID = str(_raw_chat)
else:
    print(f"Ignoring non-numeric TELEGRAM_CHANNEL_ID={_raw_chat!r}")
    TELEGRAM_CHANNEL_ID = "-1004499950812"

PAIRS = ["XAUUSD"]
DEFAULT_RISK_PERCENT = 1.0
MOMENTUM_RISK_PERCENT = 0.75
XAU_SL_BUFFER = 20

LONDON_START = int(os.getenv("LONDON_START", "7"))
LONDON_END = int(os.getenv("LONDON_END", "16"))
NY_START = int(os.getenv("NY_START", "12"))
NY_END = int(os.getenv("NY_END", "21"))

# Scoring tiers
MIN_SIGNAL_SCORE = int(os.getenv("MIN_SIGNAL_SCORE", "75"))
WATCHLIST_SCORE = int(os.getenv("WATCHLIST_SCORE", "68"))
A_PLUS_SCORE = int(os.getenv("A_PLUS_SCORE", "85"))
MIN_RR = float(os.getenv("MIN_RR", "1.8"))
MIN_RR_TP1 = MIN_RR  # alias for older code

# Limits / cooldown
MAX_DAILY_SIGNALS_XAU = int(os.getenv("MAX_DAILY_SIGNALS_XAU", os.getenv("MAX_DAILY_SIGNALS_XAUUSD", "3")))
MAX_DAILY_SIGNALS_BTC = int(os.getenv("MAX_DAILY_SIGNALS_BTC", "3"))
MAX_SIGNALS_PER_DAY = MAX_DAILY_SIGNALS_XAU
MAX_MOMENTUM_PER_DAY = MAX_DAILY_SIGNALS_XAU
SIGNAL_COOLDOWN_MINUTES = int(os.getenv("SIGNAL_COOLDOWN_MINUTES", "90"))
NEWS_SCORE_BONUS_MAX = int(os.getenv("NEWS_SCORE_BONUS_MAX", "10"))

NEWS_BLACKOUT = os.getenv("NEWS_BLACKOUT", "false").lower() in ("1", "true", "yes")
