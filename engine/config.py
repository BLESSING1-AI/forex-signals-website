"""Configuration — daily signals for members + event trains"""
import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8821872779:AAFIZW1pIaobz9MpQek5JoxXMWwAuX38_18")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "-1004499950812")

# Daily flow for members (not only news days)
MODE = "daily"
MAX_SIGNALS_PER_DAY = 4          # strict PA setups per day
MAX_MOMENTUM_PER_DAY = 5         # small scalps for account growth
PAIRS = ["XAUUSD"]
DEFAULT_RISK_PERCENT = 1.0
MOMENTUM_RISK_PERCENT = 0.5

XAU_SL_BUFFER = 25

# Sessions UTC — London + NY (covers most SA daytime)
LONDON_START, LONDON_END = 7, 16
NY_START, NY_END = 12, 21

MIN_RR_TP1 = 1.2                 # slightly easier so daily setups can fire
NEWS_BLACKOUT = False
