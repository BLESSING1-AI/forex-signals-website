# Hybrid AI — Gemini verification layer

## GitHub Secrets required

| Secret | Required | Purpose |
|--------|----------|---------|
| `TELEGRAM_BOT_TOKEN` | Yes | Existing bot token |
| `GEMINI_API_KEY` | Yes for AI | Google AI Studio API key |

Optional env (workflow or local):

| Variable | Default | Meaning |
|----------|---------|---------|
| `GEMINI_MODEL` | `gemini-2.0-flash` | Model id from AI Studio |
| `AI_ENABLED` | auto (on if key set) | `true` / `false` |
| `AI_STRICT` | `true` | Fail/REJECT cannot become live signals |
| `DRY_RUN` | `false` | Log only — no Telegram trade posts |
| `GEMINI_TIMEOUT_SEC` | `20` | Request timeout |
| `GEMINI_MAX_RETRIES` | `2` | Retry budget |
| `AI_CACHE_TTL_SEC` | `300` | Cache identical setups |

## How to add GEMINI_API_KEY

1. Open https://aistudio.google.com/apikey and create an API key.
2. GitHub repo → Settings → Secrets and variables → Actions.
3. New repository secret name: `GEMINI_API_KEY`, value: your key.

Never commit the key. Never put it in frontend JavaScript.

## Behaviour (Phase 1)

1. Deterministic engine scores setup and sets entry / SL / TP (AI cannot change prices).
2. Regime module labels market condition (trending / ranging / consolidation / volatility / potential reversal).
3. Gemini returns APPROVE / REJECT / WATCH JSON with confidence and reasons.
4. `AI_STRICT=true`: only APPROVE with successful AI response (`ai_status` ok/cached) becomes a live signal.
5. If API fails, times out, or key missing: setup is **not** silently approved.
6. Telegram and website payload include AI decision, confidence, regime, and strategy name.

## Data note

Gold uses Coinbase **PAXG-USD** as a proxy. It is not identical to broker XAUUSD spreads/quotes.
