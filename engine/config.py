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
        "sl_buffer": float(os.getenv("XAU_SL_BUFFER", "18")),
        "max_daily": int(os.getenv("MAX_DAILY_SIGNALS_XAU", "4")),
        # Softer so normal day moves can score (was too strict)
        "disp_strong": 16.0,
        "disp_solid": 9.0,
        "disp_ok": 4.0,
        "disp_vote": 5.0,
        "risk_min": 4.0,
        "risk_max": 100.0,
        "vol_abs_strong": 14.0,
        "vol_abs_mid": 8.0,
        "decimals": 2,
        "session_mode": "fx",
    },
    "BTCUSD": {
        "product": "BTC-USD",
        "sl_buffer": float(os.getenv("BTC_SL_BUFFER", "120")),
        "max_daily": int(os.getenv("MAX_DAILY_SIGNALS_BTC", "4")),
        "disp_strong": 350.0,
        "disp_solid": 160.0,
        "disp_ok": 60.0,
        "disp_vote": 70.0,
        "risk_min": 50.0,
        "risk_max": 2500.0,
        "vol_abs_strong": 280.0,
        "vol_abs_mid": 140.0,
        "decimals": 2,
        "session_mode": "crypto",
    },
}

PAIRS = list(SYMBOLS.keys())
DEFAULT_RISK_PERCENT = float(os.getenv("DEFAULT_RISK_PERCENT", "1.0"))
MOMENTUM_RISK_PERCENT = 0.75
XAU_SL_BUFFER = SYMBOLS["XAUUSD"]["sl_buffer"]

# UTC hours — London + NY overlap bias for gold day trades
LONDON_START = int(os.getenv("LONDON_START", "7"))
LONDON_END = int(os.getenv("LONDON_END", "16"))
NY_START = int(os.getenv("NY_START", "12"))
NY_END = int(os.getenv("NY_END", "21"))

# Day-trade thresholds (was 75 — too quiet)
MIN_SIGNAL_SCORE = int(os.getenv("MIN_SIGNAL_SCORE", "68"))
WATCHLIST_SCORE = int(os.getenv("WATCHLIST_SCORE", "58"))
A_PLUS_SCORE = int(os.getenv("A_PLUS_SCORE", "82"))
MIN_RR = float(os.getenv("MIN_RR", "1.6"))
MIN_RR_TP1 = MIN_RR

MAX_DAILY_SIGNALS_XAU = SYMBOLS["XAUUSD"]["max_daily"]
MAX_DAILY_SIGNALS_BTC = SYMBOLS["BTCUSD"]["max_daily"]
MAX_SIGNALS_PER_DAY = MAX_DAILY_SIGNALS_XAU
MAX_MOMENTUM_PER_DAY = MAX_DAILY_SIGNALS_XAU
SIGNAL_COOLDOWN_MINUTES = int(os.getenv("SIGNAL_COOLDOWN_MINUTES", "60"))
NEWS_SCORE_BONUS_MAX = int(os.getenv("NEWS_SCORE_BONUS_MAX", "10"))
NEWS_BLACKOUT = os.getenv("NEWS_BLACKOUT", "false").lower() in ("1", "true", "yes")
