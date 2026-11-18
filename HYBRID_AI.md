# Hybrid AI Trading Intelligence — Setup

## Architecture

1. **Deterministic engine** scores structure/momentum and **owns all prices** (entry, SL, TP).
2. **Regime module** labels trend / range / volatility.
3. **Gemini AI** returns APPROVE / REJECT / WATCH JSON only — **never invents levels**.
4. **AI_STRICT=true** (default): only APPROVE with successful AI response becomes a live signal.
5. Telegram + website receive the final result.

## GitHub Secrets

| Secret | Required |
|--------|----------|
| `TELEGRAM_BOT_TOKEN` | Yes |
| `GEMINI_API_KEY` | Yes for AI |

### Add GEMINI_API_KEY

1. https://aistudio.google.com/apikey — create key  
2. Repo → Settings → Secrets and variables → Actions  
3. Name: `GEMINI_API_KEY`  

Optional workflow env (already in `signal-engine.yml`):

- `GEMINI_MODEL=gemini-2.0-flash` (change when Google renames models)
- `AI_STRICT=true`
- `DRY_RUN=false` (set `true` to log without posting trades)

## Local test

```bash
cd engine
pip install -r requirements.txt
python -m unittest test_ai_gate test_regime test_scoring -v
DRY_RUN=true AI_ENABLED=false python signal_engine.py
```

## Safety

- No broker auto-execution
- PAXG-USD is a **proxy** for gold, not broker XAUUSD
- AI failure ≠ silent approve
- API key never in frontend
