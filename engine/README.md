# Autonomous Price Action Signal Engine

Strict Mode • XAUUSD only • 1–2 high-quality signals per day max

## Framework Implemented

1. **HTF Bias (D1 + H4)**  
   Clear structure only (Higher Highs/Higher Lows or Lower Highs/Lower Lows). Conflict = no trade.

2. **Confirmation (M15 / M5)**  
   Bullish/Bearish Engulfing or Pin Bar on the closed candle.

3. **Stop Loss**  
   Structure-based + gold volatility buffer (25 points).

4. **Targets**  
   TP1 ≈ 1.5R (partial + BE)  
   TP2 ≈ 3R  
   TP3 ≈ 5R

5. **Filters**  
   - London + New York sessions only  
   - Max 2 signals per day  
   - Minimum RR checks

## Current Limitations (Phase 1)

- Uses Yahoo Finance Gold futures (GC=F) as a free proxy for XAUUSD.  
  For production we should switch to a proper real-time XAUUSD feed.
- Order Block / Supply-Demand zone detection is simplified (structure swings only).
- No economic calendar integration yet (news blackout is manual).

## How to Run Locally

```bash
cd engine
pip install -r requirements.txt
python signal_engine.py
```

## Next Improvements

- Better data source (Twelve Data / broker API / Polygon)
- Proper Order Block & Liquidity Sweep detection
- Economic calendar filter
- Persistent signal storage + website auto-update
- GitHub Actions or Vercel Cron for unattended runs
