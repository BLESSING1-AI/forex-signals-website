# Autonomous Price Action + Event Engine

## Two signal types

### 1. Technical Price Action (Strict Mode)
- D1 + H4 bias must agree
- M15/M5 Engulfing or Pin Bar confirmation
- Structure SL + gold buffer
- 3 TPs (1.5R / 3R / 5R)
- Max 2 technical signals per day
- London + New York only

### 2. Event Signals (High Impact)
- NFP, CPI, FOMC, PPI, Retail Sales, GDP, Unemployment, ISM/PMI, Core PCE, etc.
- **PRE-EVENT**: directional bias from HTF structure before the number
- **POST-EVENT**: directional reaction after the release (confirmation candle)
- Clear `EVENT SIGNAL (PRE/POST)` format so students know it’s news-driven
- Wider stops around news

## Data
- Gold: Coinbase PAXG-USD (free)
- Calendar: biquote.io free high-impact calendar (no key)

## Runs automatically
GitHub Actions every 30 minutes.

Manual test: Actions → Price Action Signal Engine → Run workflow
