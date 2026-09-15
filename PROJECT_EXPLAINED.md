# MarketResearch — Full Project Explanation

This document explains **what this project is**, **how every piece works**, **what we built**, and **where algorithmic trading fits today**. It is written for beginners who want the full picture.

---

## 1. What is this project in one sentence?

**MarketResearch** is a local research dashboard that connects to your Zerodha Kite account, securely stores your API session on the server, and scans Nifty 100 stocks for **SMA (Simple Moving Average) crossover signals** so you can study market trends faster than doing it by hand.

It is **not** a fully automated trading bot yet.  
Right now it is a **market research + signal generation** system — the first and most important layer of algo trading.

---

## 2. The problem this project solves

Manually checking 100 large Indian stocks every day is slow and error-prone:

1. Open charts one by one
2. Draw or eyeball moving averages
3. Decide if a crossover happened
4. Remember which stocks crossed recently
5. Rank which signals are newest

This project automates that research loop:

- Pulls the official **Nifty 100** stock list
- Downloads daily price history from **Zerodha Kite Connect**
- Calculates **short SMA** and **long SMA**
- Detects **bullish** and **bearish** crossovers
- Ranks results by **most recent crossover date**
- Shows everything in a clean dark dashboard (and also as a CSV from the original script)

---

## 3. High-level architecture

The project has three layers:

```text
┌────────────────────────────────────────────────────────────┐
│  Frontend (React + Vite)                                   │
│  - Login page                                              │
│  - Dashboard                                               │
│    - User tab                                              │
│    - Signals tab                                           │
└───────────────────────────┬────────────────────────────────┘
                            │ HTTP /api/*
                            ▼
┌────────────────────────────────────────────────────────────┐
│  Backend (Python FastAPI)                                  │
│  - Auth (login / status / logout)                          │
│  - Profile                                                 │
│  - SMA crossover scanner                                   │
│  - Saves access token server-side only                     │
└───────────────────────────┬────────────────────────────────┘
                            │ Kite Connect SDK
                            ▼
┌────────────────────────────────────────────────────────────┐
│  Zerodha Kite Connect APIs                                 │
│  - Login / session                                         │
│  - Profile                                                 │
│  - Instruments (symbol → token map)                        │
│  - Historical daily candles                                │
└────────────────────────────────────────────────────────────┘
```

There is also a standalone research script:

- `nifty 100_sma_scanner.py`  
  A beginner-friendly one-file scanner that does the same core SMA logic and writes `nifty 100_sma_signals.csv`.

---

## 4. Project folders and what each part does

```text
MarketResearch/
├── frontend/                     # Browser UI
│   └── src/
│       ├── pages/                # Login + Dashboard screens
│       ├── components/dashboard/ # User tab + Signals tab
│       ├── api/                  # Calls backend APIs
│       ├── context/              # Auth state for the app
│       └── styles/theme.css      # Dark theme customization
│
├── backend/                      # Server API
│   └── app/
│       ├── main.py               # FastAPI app entry
│       ├── config.py             # Paths, CORS, session file
│       ├── schemas.py            # Request/response models
│       ├── routes/               # HTTP endpoints
│       └── services/             # Business logic
│           ├── kite_session.py   # Login + token storage
│           └── sma_scanner.py    # Nifty 100 SMA scanner
│
├── nifty 100_sma_scanner.py      # Standalone CLI scanner
├── nifty 100_sma_signals.csv     # Latest CLI scan output
├── credentials.txt               # Local API key/secret notes
└── README.md                     # Setup / run guide
```

### Important security idea

- `api_key`, `api_secret`, and `request_token` are entered for login
- Kite returns an **access token**
- That access token is saved only on the backend in:

```text
backend/.kite_session.json
```

- The browser **never** receives or displays the access token
- On backend restart, the server tries to restore that session so local development is smoother

---

## 5. What happens when you use the app (step by step)

### Step A — Start the system

1. Start backend:

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

2. Start frontend:

```bash
cd frontend
npm run dev
```

3. Open:

```text
http://localhost:5173
```

The frontend talks to `/api/...`, and Vite proxies those calls to the FastAPI backend on port `8000`.

### Step B — Login flow (Zerodha Kite Connect)

Zerodha does not let apps keep your password. The flow is:

1. You open Kite login using your API key
2. After approval, Kite redirects with a one-time `request_token`
3. You paste:
   - API Key
   - API Secret
   - Request Token
4. Frontend sends those values to `POST /api/auth/login`
5. Backend uses Kite SDK `generate_session(...)`
6. Backend receives `access_token`
7. Backend stores it in memory + `.kite_session.json`
8. Frontend only gets safe info like:
   - login success
   - user name
   - user id

Then the app navigates to the dashboard.

### Step C — User tab

The User tab calls `GET /api/profile`.

Backend uses the saved access token and asks Kite for your profile. The UI shows:

- User Name
- User ID
- Products (example: CNC, MIS, NRML)
- Exchanges (example: NSE, BSE, NFO)

This proves the session is alive and the API connection works.

### Step D — Signals tab (core research feature)

On the Signals tab you can set:

- **Short SMA** (default `6`)
- **Long SMA** (default `30`)
- **Lookback Days** (default `400`)
- **Max Stocks** (default `100`)

When you click **Generate Signals**, frontend calls:

```text
POST /api/signals/sma-crossover
```

Backend then runs the full scanner pipeline (explained next).

---

## 6. The SMA crossover scanner — what is happening technically

This is the heart of the project.

### 6.1 Load Nifty 100 constituents

The scanner downloads the official Nifty Indices CSV (Nifty 100 list), typically from NSE archives:

```text
https://archives.nseindia.com/content/indices/ind_nifty100list.csv
```

From that file it extracts:

- Symbol / Ticker (example: `RELIANCE`, `TCS`)
- Company name

Why this matters:  
You are scanning a defined universe (large liquid Indian stocks), not random tickers.

### 6.2 Map symbols to Kite instrument tokens

Kite historical APIs usually need an **instrument token**, not just `"RELIANCE"`.

So the backend:

1. Downloads NSE instrument master from Kite
2. Filters equity (`EQ`) instruments
3. Builds a map like:

```text
RELIANCE -> 738561
TCS      -> 2953217
...
```

### 6.3 Fetch daily historical candles

For each mapped stock, backend requests daily OHLC history for your lookback window (example: last 400 calendar days).

Each candle includes values like:

- date
- open
- high
- low
- close
- volume

The scanner mainly uses **close** prices for SMA calculation.

### 6.4 Calculate SMA 6 and SMA 30 (or your chosen periods)

A **Simple Moving Average (SMA)** is the average closing price over the last N days.

Examples:

- SMA 6 = average of last 6 closes
- SMA 30 = average of last 30 closes

Interpretation (simplified):

- Short SMA reacts faster to recent price moves
- Long SMA reacts slower and represents the broader trend

### 6.5 Detect bullish and bearish crossovers

A crossover is when the short SMA crosses the long SMA.

#### Bullish crossover

- Yesterday: short SMA was **at or below** long SMA
- Today: short SMA is **above** long SMA

Meaning (common interpretation): short-term momentum turned stronger than the medium-term trend. Traders often treat this as a potential **buy / strength** signal.

#### Bearish crossover

- Yesterday: short SMA was **at or above** long SMA
- Today: short SMA is **below** long SMA

Meaning (common interpretation): short-term momentum weakened relative to the medium-term trend. Traders often treat this as a potential **sell / weakness** signal.

For each stock, the scanner keeps the **most recent** crossover in the lookback window.

### 6.6 Rank by most recent crossover date

All found signals are sorted so newest events appear first.

Example output columns:

| Rank | Ticker | Company | Crossover Type | Crossover Date | Close | SMA 6 | SMA 30 |
|------|--------|---------|----------------|----------------|-------|-------|--------|
| 1 | AXISBANK | Axis Bank Ltd. | Bearish | 2026-09-15 | 1224.50 | 1244.32 | 1247.43 |
| 8 | MAXHEALTH | Max Healthcare... | Bullish | 2026-09-15 | 1040.10 | 1023.15 | 1021.44 |

You already have a generated sample in:

```text
nifty 100_sma_signals.csv
```

That CSV is evidence the research pipeline works end-to-end.

---

## 7. Frontend experience in detail

### Login page

Purpose:

- Collect Kite credentials and request token
- Send them to backend
- Never display access token

### Dashboard

Tabs:

1. **User**
   - Confirms authentication and profile connectivity
2. **Signals**
   - Parameter form
   - Generate button
   - Loading state while scanning
   - Summary counts (signals / scanned / bullish / bearish)
   - Polished results table

UI style:

- Dark mode by default
- Clean professional layout
- Easy to customize via CSS variables in `frontend/src/styles/theme.css`

---

## 8. Backend APIs (what the server exposes)

| Method | Endpoint | What it does |
|--------|----------|--------------|
| `POST` | `/api/auth/login` | Creates Kite session and saves access token server-side |
| `GET` | `/api/auth/status` | Checks if a valid session exists/restored |
| `POST` | `/api/auth/logout` | Clears session and deletes saved token file |
| `GET` | `/api/profile` | Returns user profile fields from Kite |
| `POST` | `/api/signals/sma-crossover` | Runs Nifty 100 SMA crossover scanner |
| `GET` | `/api/health` | Simple health check |

Interactive API docs (when backend is running):

```text
http://127.0.0.1:8000/docs
```

---

## 9. What we achieved so far

### Achievement 1 — Working Zerodha integration

- Login using Kite Connect
- Secure server-side token storage
- Session restore for local development
- Profile fetch from live Kite APIs

### Achievement 2 — Research-grade signal scanner

- Official Nifty 100 universe
- Historical candle download
- Configurable SMA periods
- Bullish/bearish crossover detection
- Ranking by recency

### Achievement 3 — Two usable interfaces

1. **CLI script** (`nifty 100_sma_scanner.py`) for quick offline/script-style research
2. **Web dashboard** for interactive daily use

### Achievement 4 — Beginner-friendly full-stack foundation

- React + Vite frontend
- FastAPI backend
- Clear separation of UI / API / trading logic
- Clean dark UI that can grow into more tools

### Achievement 5 — Real output already produced

The file `nifty 100_sma_signals.csv` shows concrete ranked crossover signals across Nifty 100 names. That means the core algo research idea is not just theoretical — it already runs on real market data.

---

## 10. Where does “algo trading” help right now?

This is the most important conceptual section.

### What algo trading usually means

Algorithmic trading means using rules/code to:

1. Observe market data
2. Detect conditions (signals)
3. Decide actions (buy/sell/hold)
4. Optionally place/manage orders automatically
5. Measure performance and risk

A complete algo system often looks like:

```text
Data → Signals → Decision Rules → Order Execution → Risk Control → Reporting
```

### What this project already covers

| Algo stage | Status in this project | Notes |
|------------|------------------------|-------|
| Market data access | Done | Via Kite historical candles |
| Universe selection | Done | Nifty 100 official list |
| Indicator calculation | Done | SMA short/long |
| Signal generation | Done | Bullish/bearish crossover |
| Ranking / prioritization | Done | Most recent first |
| Human review UI | Done | Dashboard Signals tab |
| Strategy backtesting | Not yet | No historical performance simulation |
| Position sizing / risk rules | Not yet | No capital allocation logic |
| Auto order placement | Not yet | No buy/sell API calls |
| Portfolio tracking | Not yet | No holdings/PnL module |

### So what did algo trading help with *right now*?

Right now, algo methods help you with **speed, consistency, and coverage**:

1. **Speed**
   - Scanning ~100 stocks manually can take hours
   - Code can do it in minutes

2. **Consistency**
   - Humans forget rules or apply them unevenly
   - The algorithm always uses the same crossover definition

3. **Coverage**
   - You can watch the full Nifty 100 universe every day
   - You are less likely to miss a fresh crossover

4. **Prioritization**
   - Ranking by latest crossover date answers: “What changed most recently?”
   - That is useful for daily research focus

5. **Foundation for future automation**
   - Once signals are reliable, you can later add:
     - filters (volume, trend confirmation, sector)
     - backtests
     - paper trading
     - then carefully, live order execution

### Honest boundary (important)

Today this project is best described as:

> **Algorithmic market research / signal scanner**

Not yet:

> Fully automated algo trading system that places live trades

That is actually a healthy place to start. Most serious traders build signal quality and process discipline before enabling auto-execution.

---

## 11. How to think about the SMA strategy (practical view)

SMA crossover is a classic trend-following idea:

- Bullish crossover = possible momentum shift upward
- Bearish crossover = possible momentum shift downward

But crossovers are **not guarantees**.

Common limitations:

- Late signals (moving averages lag price)
- Whipsaws in sideways markets (many false crosses)
- No built-in stop-loss or target logic yet
- No transaction cost / slippage modeling yet

So use current output as:

- A **watchlist generator**
- A **research shortlist**
- A starting point for chart confirmation

Not as automatic “buy immediately” instructions.

---

## 12. End-to-end story of what we built in this journey

1. Started with a single Python scanner for Nifty 100 SMA crossovers
2. Produced ranked CSV signals
3. Built a FastAPI backend for secure Kite login and session reuse
4. Built a React dashboard with User profile view
5. Upgraded the dashboard with a Signals tab connected to the live scanner API
6. Kept access tokens server-side for safer local development

In short: we moved from a one-off research script to a small but real **research workstation**.

---

## 13. What you can do next (natural roadmap)

If you continue building toward deeper algo trading, a sensible order is:

1. **Better signal quality**
   - Add volume filter
   - Require price above/below long SMA
   - Add RSI / MACD confirmation

2. **Backtesting**
   - Simulate historical trades from past crossovers
   - Measure win rate, drawdown, average return

3. **Paper trading**
   - Log virtual trades without real money

4. **Risk engine**
   - Max risk per trade
   - Max open positions
   - Daily loss limit

5. **Execution (advanced, careful)**
   - Place orders via Kite only after risk checks
   - Start with small size and strong logging

---

## 14. Quick glossary

- **Kite Connect**: Zerodha’s developer API for market data and trading features
- **Request token**: One-time login code from Kite redirect URL
- **Access token**: Session key used for API calls (stored only on backend here)
- **Instrument token**: Kite’s numeric ID for a tradable symbol
- **Nifty 100**: Index of 100 large Indian companies
- **SMA**: Simple Moving Average of closing prices
- **Crossover**: When one indicator line crosses another
- **Bullish / Bearish**: Strength vs weakness interpretation of a signal
- **Algo trading**: Using coded rules for market analysis and optionally trade execution

---

## 15. Bottom line

This project gives you a practical, beginner-friendly path into algorithmic trading by focusing on the part that matters first:

> **Turn raw market data into clear, ranked research signals.**

You now have:

- Secure broker API login
- A reusable local dashboard
- A working Nifty 100 SMA crossover engine
- Real signal output you can review every day

That is a solid foundation. The next leap is not “place orders immediately,” but “prove which signals are worth acting on.”
