# Autonomous Price Action Engine

Strict Mode • XAUUSD only • Max 2 signals/day

## How it works
1. D1 + H4 must agree on bias (HH/HL or LH/LL)
2. M15/M5 must show Engulfing or Pin Bar confirmation
3. Structure-based SL + 25pt gold buffer
4. 3 TPs at 1.5R / 3R / 5R
5. Only London + New York sessions

## Data source
Coinbase public API → PAXG-USD (free gold proxy, no API key needed)

## Automatic running (GitHub Actions)
The engine runs automatically every 30 minutes via GitHub Actions.

Workflow file: `.github/workflows/signal-engine.yml`

You can also trigger it manually:
1. Go to the repo on GitHub
2. Click **Actions**
3. Select **Price Action Signal Engine**
4. Click **Run workflow**

## Optional secrets (recommended)
For better security, add these in GitHub → Settings → Secrets and variables → Actions:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHANNEL_ID`

If not set, the engine uses the values already in `config.py`.

## Run locally
```bash
cd engine
pip install -r requirements.txt
python signal_engine.py
```

## Notes
- The engine itself still checks session times and daily signal limit.
- No forced trades — only high-quality aligned setups are posted.
