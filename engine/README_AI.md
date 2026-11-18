# Hybrid AI Phase 1 — Gemini setup

## GitHub Secrets required

| Secret | Required | Purpose |
|--------|----------|---------|
| `TELEGRAM_BOT_TOKEN` | Yes | Existing bot token |
| `GEMINI_API_KEY` | Yes for AI | Google AI Studio API key |

Optional env:

| Variable | Default | Meaning |
|----------|---------|---------|
| `GEMINI_MODEL` | `gemini-2.0-flash` | Model id from AI Studio |
| `AI_ENABLED` | auto (on if key set) | `true` / `false` |
| `AI_STRICT` | `true` | Fail/REJECT cannot become live signals |
| `DRY_RUN` | `false` | Log only — no Telegram trade posts |

## How to add GEMINI_API_KEY

1. Open https://aistudio.google.com/apikey and create an API key.
2. GitHub repo → Settings → Secrets and variables → Actions.
3. New repository secret name: `GEMINI_API_KEY`, value: your key.

Never commit the key. Never put it in frontend JS.

## Behaviour

1. Deterministic engine scores setup and sets entry / SL / TP (AI cannot change prices).
2. Regime module labels market condition.
3. Gemini returns APPROVE / REJECT / WATCH JSON.
4. AI_STRICT=true: only APPROVE with successful AI response becomes a live signal.
5. If API fails or key missing: setup is **not** silently approved.
