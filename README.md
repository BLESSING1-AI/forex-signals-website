# Price Action Signals Website

A clean, mobile-friendly website for sharing your price-action forex setups (especially XAUUSD) with beginners.

## How to update signals

1. Open `index.html`
2. Find the `const signals = [ ... ]` array near the bottom
3. Edit / add / remove objects
4. Commit and push — the site updates automatically if connected to Vercel

### Signal object format

```js
{
  pair: "XAUUSD",
  direction: "Sell",          // or "Buy"
  entry: "4200–4205",
  stopLoss: "4112",
  targets: ["4197", "4194", "4191", "4188", "4185", "4182", "4179", "4176"],
  note: "Wait for confirmation and manage your risk accordingly.",
  status: "active",           // active | closed | cancelled
  postedAt: "2026-10-13"
}
```

## Deploy

- Push this repo to GitHub
- Import the repo on [Vercel](https://vercel.com) (free)
- Every push to `main` will redeploy the site

## Local preview

Just open `index.html` in a browser. No build step required.
