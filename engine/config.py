"""Configuration — XAU (strict pullback) + BTC (momentum OK)"""
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
        # Wider buffer — gold spikes stop out tight SLs
        "sl_buffer": float(os.getenv("XAU_SL_BUFFER", "35")),
        "max_daily": int(os.getenv("MAX_DAILY_SIGNALS_XAU", "2")),
        "disp_strong": 18.0,
        "disp_solid": 10.0,
        "disp_ok": 5.0,
        "disp_vote": 6.0,
        # Minimum risk distance in price — stop noise stops
        "risk_min": 28.0,
        "risk_max": 90.0,
        "vol_abs_strong": 16.0,
        "vol_abs_mid": 9.0,
        "decimals": 2,
        "session_mode": "fx",
        # Gold-only quality gates
        "min_score": int(os.getenv("XAU_MIN_SCORE", "72")),
        "require_htf": True,
        "prefer_pullback": True,
        "allow_breakout": False,
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
        "min_score": int(os.getenv("BTC_MIN_SCORE", "62")),
        "require_htf": False,
        "prefer_pullback": False,
        "allow_breakout": True,
    },
}

PAIRS = list(SYMBOLS.keys())
DEFAULT_RISK_PERCENT = float(os.getenv("DEFAULT_RISK_PERCENT", "1.0"))
MOMENTUM_RISK_PERCENT = 0.75
XAU_SL_BUFFER = SYMBOLS["XAUUSD"]["sl_buffer"]

# Gold: London + NY only (skip dead Asia chop that stops out)
LONDON_START = int(os.getenv("LONDON_START", "7"))
LONDON_END = int(os.getenv("LONDON_END", "16"))
NY_START = int(os.getenv("NY_START", "12"))
NY_END = int(os.getenv("NY_END", "20"))

MIN_SIGNAL_SCORE = int(os.getenv("MIN_SIGNAL_SCORE", "62"))
WATCHLIST_SCORE = int(os.getenv("WATCHLIST_SCORE", "55"))
A_PLUS_SCORE = int(os.getenv("A_PLUS_SCORE", "80"))
MIN_RR = float(os.getenv("MIN_RR", "1.6"))
MIN_RR_TP1 = MIN_RR

MAX_DAILY_SIGNALS_XAU = SYMBOLS["XAUUSD"]["max_daily"]
MAX_DAILY_SIGNALS_BTC = SYMBOLS["BTCUSD"]["max_daily"]
MAX_SIGNALS_PER_DAY = MAX_DAILY_SIGNALS_XAU
MAX_MOMENTUM_PER_DAY = MAX_DAILY_SIGNALS_XAU
SIGNAL_COOLDOWN_MINUTES = int(os.getenv("SIGNAL_COOLDOWN_MINUTES", "60"))
NEWS_SCORE_BONUS_MAX = int(os.getenv("NEWS_SCORE_BONUS_MAX", "10"))
NEWS_BLACKOUT = os.getenv("NEWS_BLACKOUT", "false").lower() in ("1", "true", "yes")
