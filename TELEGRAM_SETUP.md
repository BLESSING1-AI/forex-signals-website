# Telegram Bot & Channel Setup Guide

Follow these steps exactly. Once done, send me the **Bot Token** and **Channel ID** so we can connect the autonomous engine.

---

## Step 1 – Create the Channel

1. Open Telegram
2. Tap the pencil / new message icon → **New Channel**
3. Name it exactly:  
   **Price Action Signals – Gold & FX**
4. Description (recommended):
   ```
   Strict multi-timeframe price action signals for XAUUSD.
   HTF bias → Zone → M15/M5 confirmation.
   3-TP system with breakeven. Educational only. Risk 1% max.
   ```
5. Make it **Public** (so students can join easily) or Private (you control who joins)
6. Create the channel

---

## Step 2 – Create the Bot via BotFather

1. In Telegram search for **@BotFather**
2. Send `/newbot`
3. Choose a display name, e.g.:  
   `Price Action Signals Bot`
4. Choose a username ending in `bot`, e.g.:  
   `PriceActionGoldBot` or `PASignalsGoldBot`
5. BotFather will reply with your **HTTP API Token**.  
   It looks like:  
   `7123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw`

   **Copy and save this token securely.**

---

## Step 3 – Add the Bot to the Channel as Admin

1. Open your new channel → tap the channel name at the top
2. Tap **Administrators** → **Add Admin**
3. Search for the bot username you just created and add it
4. Give it permission to **Post Messages** (at minimum)
5. Save

---

## Step 4 – Get the Channel ID

### Method A (Recommended – Public Channel)
If the channel is public, the Channel ID is simply:
```
@YourChannelUsername
```
(Example: `@PriceActionSignalsGold`)

### Method B (Private Channel or to get numeric ID)
1. Add the bot **@userinfobot** or **@getidsbot** to the channel temporarily
2. Or forward any message from the channel to **@userinfobot**
3. It will reply with the numeric ID (usually starts with `-100`)

Example numeric ID: `-1001234567890`

---

## Step 5 – Send me the credentials

Once you have both, reply here with:

```
Bot Token: 7123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw
Channel ID: @PriceActionSignalsGold
```
or
```
Bot Token: ...
Channel ID: -1001234567890
```

I will then connect the autonomous signal engine so it can post automatically in the exact format:

```
🚨 PRICE ACTION SIGNAL: BUY XAUUSD 🚨

📍 Entry Zone: 2642.50 - 2644.00
🛑 Stop Loss: 2634.50 (Structure SL)

🎯 Take Profit 1: 2650.00 (Partial close + Move SL to BE)
🎯 Take Profit 2: 2658.00
🎯 Take Profit 3: 2670.00

📊 Setup Context:
• D1 / H4 Bullish Alignment
• M15 Liquidity Sweep & Bullish Engulfing Rejection at Support Zone
• Recommended Risk: 1% per trade
```

---

## Important Notes

- Never share the Bot Token publicly.
- The bot only needs permission to post messages.
- Students only need to join the channel once.
- The website will also display the same signals automatically.
