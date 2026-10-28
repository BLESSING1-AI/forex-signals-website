"""Configuration — XAU + BTC scored system"""
import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
if not TELEGRAM_BOT_TOKEN:
    print("WARNING: TELEGRAM_BOT_TOKEN missing — set GitHub secret")

_raw_chat = os.getenv("TELEGRAM_CHANNEL_ID", "-1004499950812")
if _raw_chat and str(_raw_chat).lstrip("-").isdigit():
    TELEGRAM_CHANNEL_ID = str(_raw_chat)
else:
    TELEGRAM_CHANNEL_ID = "-1004499950812"

SYMBOLS = {
    "XAUUSD": {
        "product": "PAXG-USD",
        "sl_buffer": float(os.getenv("XAU_SL_BUFFER", "20")),
        "max_daily": int(os.getenv("MAX_DAILY_SIGNALS_XAU", "3")),
        "disp_strong": 22.0,
        "disp_solid": 12.0,
        "disp_ok": 6.0,
        "disp_vote": 8.0,
        "risk_min": 6.0,
        "risk_max": 90.0,
        "vol_abs_strong": 20.0,
        "vol_abs_mid": 12.0,
        "decimals": 2,
        "session_mode": "fx",
    },
    "BTCUSD": {
        "product": "BTC-USD",
        "sl_buffer": float(os.getenv("BTC_SL_BUFFER", "150")),
        "max_daily": int(os.getenv("MAX_DAILY_SIGNALS_BTC", "3")),
        "disp_strong": 450.0,
        "disp_solid": 220.0,
        "disp_ok": 90.0,
        "disp_vote": 100.0,
        "risk_min": 80.0,
        "risk_max": 2500.0,
        "vol_abs_strong": 350.0,
        "vol_abs_mid": 180.0,
        "decimals": 2,
        "session_mode": "crypto",
    },
}

PAIRS = list(SYMBOLS.keys())
DEFAULT_RISK_PERCENT = float(os.getenv("DEFAULT_RISK_PERCENT", "1.0"))
MOMENTUM_RISK_PERCENT = 0.75
XAU_SL_BUFFER = SYMBOLS["XAUUSD"]["sl_buffer"]

LONDON_START = int(os.getenv("LONDON_START", "7"))
LONDON_END = int(os.getenv("LONDON_END", "16"))
NY_START = int(os.getenv("NY_START", "12"))
NY_END = int(os.getenv("NY_END", "21"))

MIN_SIGNAL_SCORE = int(os.getenv("MIN_SIGNAL_SCORE", "75"))
WATCHLIST_SCORE = int(os.getenv("WATCHLIST_SCORE", "68"))
A_PLUS_SCORE = int(os.getenv("A_PLUS_SCORE", "85"))
MIN_RR = float(os.getenv("MIN_RR", "1.8"))
MIN_RR_TP1 = MIN_RR

MAX_DAILY_SIGNALS_XAU = SYMBOLS["XAUUSD"]["max_daily"]
MAX_DAILY_SIGNALS_BTC = SYMBOLS["BTCUSD"]["max_daily"]
MAX_SIGNALS_PER_DAY = MAX_DAILY_SIGNALS_XAU
MAX_MOMENTUM_PER_DAY = MAX_DAILY_SIGNALS_XAU
SIGNAL_COOLDOWN_MINUTES = int(os.getenv("SIGNAL_COOLDOWN_MINUTES", "90"))
NEWS_SCORE_BONUS_MAX = int(os.getenv("NEWS_SCORE_BONUS_MAX", "10"))
NEWS_BLACKOUT = os.getenv("NEWS_BLACKOUT", "false").lower() in ("1", "true", "yes")
