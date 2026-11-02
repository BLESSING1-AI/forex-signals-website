"""Configuration — XAU + BTC day-trade + event system"""
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
        "sl_buffer": float(os.getenv("XAU_SL_BUFFER", "15")),
        "max_daily": int(os.getenv("MAX_DAILY_SIGNALS_XAU", "5")),
        "disp_strong": 14.0,
        "disp_solid": 7.0,
        "disp_ok": 3.5,
        "disp_vote": 4.0,
        "risk_min": 3.5,
        "risk_max": 120.0,
        "vol_abs_strong": 12.0,
        "vol_abs_mid": 6.0,
        "decimals": 2,
        "session_mode": "fx",
    },
    "BTCUSD": {
        "product": "BTC-USD",
        "sl_buffer": float(os.getenv("BTC_SL_BUFFER", "100")),
        "max_daily": int(os.getenv("MAX_DAILY_SIGNALS_BTC", "5")),
        "disp_strong": 300.0,
        "disp_solid": 120.0,
        "disp_ok": 45.0,
        "disp_vote": 55.0,
        "risk_min": 40.0,
        "risk_max": 2500.0,
        "vol_abs_strong": 220.0,
        "vol_abs_mid": 100.0,
        "decimals": 2,
        "session_mode": "crypto",
    },
}

PAIRS = list(SYMBOLS.keys())
DEFAULT_RISK_PERCENT = float(os.getenv("DEFAULT_RISK_PERCENT", "1.0"))
MOMENTUM_RISK_PERCENT = 0.75
XAU_SL_BUFFER = SYMBOLS["XAUUSD"]["sl_buffer"]

# Gold session UTC — covers SA morning through NY (was starting too late at 07)
# 05 UTC = 07:00 SAST … 21 UTC = 23:00 SAST
LONDON_START = int(os.getenv("LONDON_START", "5"))
LONDON_END = int(os.getenv("LONDON_END", "17"))
NY_START = int(os.getenv("NY_START", "12"))
NY_END = int(os.getenv("NY_END", "21"))

MIN_SIGNAL_SCORE = int(os.getenv("MIN_SIGNAL_SCORE", "62"))
WATCHLIST_SCORE = int(os.getenv("WATCHLIST_SCORE", "52"))
A_PLUS_SCORE = int(os.getenv("A_PLUS_SCORE", "80"))
MIN_RR = float(os.getenv("MIN_RR", "1.5"))
MIN_RR_TP1 = MIN_RR

MAX_DAILY_SIGNALS_XAU = SYMBOLS["XAUUSD"]["max_daily"]
MAX_DAILY_SIGNALS_BTC = SYMBOLS["BTCUSD"]["max_daily"]
MAX_SIGNALS_PER_DAY = MAX_DAILY_SIGNALS_XAU
MAX_MOMENTUM_PER_DAY = MAX_DAILY_SIGNALS_XAU
SIGNAL_COOLDOWN_MINUTES = int(os.getenv("SIGNAL_COOLDOWN_MINUTES", "45"))
NEWS_SCORE_BONUS_MAX = int(os.getenv("NEWS_SCORE_BONUS_MAX", "10"))
NEWS_BLACKOUT = os.getenv("NEWS_BLACKOUT", "false").lower() in ("1", "true", "yes")
