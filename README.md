# MarketResearch — Zerodha Kite Quantitative Research Dashboard

React + Vite frontend with a Python FastAPI backend for **Zerodha Kite Connect** market research.

This is a **decision-support / research platform**.  
It does **not** place live Zerodha orders.

---

## What it does

1. Secure Kite login (access token stays **server-side only**)
2. User/profile view
3. Nifty 100 **scored SMA crossover research**
4. Historical **SMA backtesting** with costs + slippage

A crossover is never shown as “BUY NOW”. Labels look like:

- Strong Bullish / Good Bullish / Moderate Bullish / Weak Bullish
- Strong Bearish / …
- Avoid / Low Confidence
- Needs Confirmation / Research candidate

---

## Architecture

```text
Frontend (React)  →  FastAPI  →  Kite Connect
                         ├── auth / profile
                         ├── signals (scored scanner)
                         └── backtest (historical research)
```

### Key backend modules

| Module | Role |
|--------|------|
| `services/kite_session.py` | Login + persisted access token |
| `services/indicators.py` | SMA, RSI, ATR, volume, slope, crossover |
| `services/market_context.py` | Nifty + sector index context (cached per scan) |
| `services/signal_engine.py` | Score, classification, risk/reward research |
| `services/transaction_costs.py` | Configurable Indian equity cost model |
| `services/backtesting.py` | No-lookahead SMA backtest + combo compare |
| `services/sma_scanner.py` | Nifty 100 orchestration |

---

## Setup

### Backend

```bash
cd backend
# or use repo-root .venv
source ../.venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

### Tests

```bash
cd backend
python -m pytest tests/ -q
```

---

## APIs

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/auth/login` | Exchange request token → access token (server-only) |
| `GET` | `/api/auth/status` | Session status |
| `POST` | `/api/auth/logout` | Clear session |
| `GET` | `/api/profile` | Kite profile |
| `POST` | `/api/signals/sma-crossover` | Enhanced scored scan |
| `POST` | `/api/backtest/sma` | Historical SMA backtest |
| `GET` | `/api/health` | Health check |

Docs: http://127.0.0.1:8000/docs

---

## Signal research concepts

### SMA crossover
Short SMA crossing long SMA (bullish/bearish). Detected on completed daily bars.

### SMA spread %
`((short - long) / long) * 100` — separation feature, not a guaranteed edge.

### Long SMA slope
Rising / Flat / Falling using configurable lookback + thresholds.

### Volume confirmation
Current volume vs N-day average (`STRONG` / `NORMAL` / `WEAK`).

### RSI (Wilder)
Momentum context — not “70 = sell forever”.

### ATR
Volatility estimate for research stop distance. Does not predict direction.

### Market / sector confirmation
Nifty 50 trend once per scan; curated sector-index mapping where available.
Unmapped symbols show **Sector confirmation unavailable** (no fake data).

### Signal score (0–100)
Initial heuristic weights in `app/config.py` (`ScoreWeights`).  
**Not a probability of profit.** Explainable via `score_breakdown`.

### Risk/reward research
ATR-based stop reference + configurable R-multiple target. Informational only.

---

## Backtesting assumptions

- Signal on day **T close**
- Enter/exit at day **T+1 / E+1 open**
- Long-only research model
- Equal capital split across selected symbols
- Optional brokerage/STT/exchange/SEBI/stamp/GST model + slippage bps
- Chronological train/validation/OOS segment metadata included

Fee rates are configurable and should be verified against current Zerodha/NSE schedules.

---

## Configuration

Tunable defaults live in `backend/app/config.py`:

- SMA / RSI / ATR / volume periods
- slope thresholds
- volume / extension thresholds
- score weights and bands
- ATR stop multiplier / target R multiple
- transaction cost rates + slippage

See `.env.example` for secret/env guidance.  
Never commit `credentials.txt` or `backend/.kite_session.json`.

---

## Dashboard tabs

1. **User** — Kite profile
2. **Signals** — overview, filters, scored table, detail drawer
3. **Backtesting** — metrics, equity/drawdown charts, trades, combo compare

---

## Limitations

- Daily strategy only (not intraday)
- Sector mapping is curated, not complete for every symbol
- Score weights are heuristics until validated by backtests
- Backtest uses a stock subset for API speed
- Not investment advice; no automated order placement

---

## Disclaimer

This dashboard provides quantitative market-research signals based on historical market data and configurable trading rules. Signals, scores, stop references and targets are informational and are not guarantees of future performance or investment advice.
