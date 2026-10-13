# Autonomous Price Action Engine

Strict Mode • XAUUSD only • Max 2 signals/day

## How it works
1. D1 + H4 must agree on bias (HH/HL or LH/LL)
2. M15/M5 must show Engulfing or Pin Bar confirmation
3. Structure-based SL + 25pt gold buffer
4. 3 TPs at 1.5R / 3R / 5R
5. Only London + New York sessions

## Data
Coinbase public API → PAXG-USD (free gold proxy)

## Run locally
```bash
cd engine
pip install -r requirements.txt
python signal_engine.py
```

## Next
- GitHub Actions / cron so it runs while you are offline
- Better Order Block + Liquidity Sweep detection
- Website auto-update when a signal is posted
