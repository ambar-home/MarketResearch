# MarketResearch — Full Project Explanation (Updated)

This document is the **complete, up-to-date explanation** of the MarketResearch project after the quantitative-signal and backtesting upgrades.

It covers:

1. What the project is now
2. Architecture and every major module
3. Authentication and security
4. How the enhanced signal pipeline works
5. Scoring, filters, and the Signals UI
6. Backtesting and transaction costs
7. How to run and verify everything
8. **How to use this project carefully** (so you do not treat signals as guaranteed predictions)
9. Limitations and recommended next steps

---

## 1. What this project is (current version)

**MarketResearch** is a local **quantitative market-research and decision-support dashboard**.

It connects to your **Zerodha Kite Connect** account and helps you:

- Scan **Nifty 100** stocks using daily historical candles
- Detect **SMA crossovers** (short vs long)
- Enrich each crossover with:
  - SMA spread
  - Long-SMA slope / trend quality
  - Price vs long SMA
  - Volume confirmation
  - RSI momentum context
  - ATR volatility
  - Nifty market confirmation
  - Sector confirmation (when a curated mapping exists)
  - Research stop / target / reward-risk framework
- Produce an explainable **Signal Quality Score (0–100)**
- Classify signals as Strong / Good / Moderate / Weak / Avoid
- Rank by **score first**, then recency
- Run **historical SMA backtests** with costs and slippage
- Compare multiple SMA combinations

### What it is not

- Not a live auto-trading bot
- Not a guaranteed prediction engine
- Not investment advice
- Not an intraday/hourly trading system (current strategy is **daily**)

A high score means:

> “This setup aligns well with our configured research rules.”

It does **not** mean:

> “87% chance this stock will go up.”

---

## 2. Evolution of the project

### Earlier version

```text
SMA crossover → Bullish / Bearish → rank by date
```

### Current version

```text
Market Data
    ↓
SMA Crossover
    ↓
Trend Quality (long SMA slope, price vs long SMA)
    ↓
Volume Confirmation
    ↓
Momentum Confirmation (RSI)
    ↓
Market Confirmation (Nifty 50)
    ↓
Sector Confirmation (when available)
    ↓
Extension + ATR risk research
    ↓
Signal Quality Score + breakdown
    ↓
STRONG / GOOD / MODERATE / WEAK / AVOID
    ↓
Human research candidate (not auto-buy)
```

Also added:

- Backtesting tab + API
- Transaction-cost model
- Strategy comparison across SMA pairs
- Unit tests for indicators, scoring, and backtest mechanics

---

## 3. High-level architecture

```text
┌──────────────────────────────────────────────────────────────┐
│ Frontend (React + Vite + TypeScript)                         │
│  Login                                                       │
│  Dashboard                                                   │
│    ├── User tab                                              │
│    ├── Signals tab (scored research + filters + drawer)      │
│    └── Backtesting tab (metrics + equity/drawdown charts)    │
└───────────────────────────────┬──────────────────────────────┘
                                │ /api/*  (Vite proxy → :8000)
                                ▼
┌──────────────────────────────────────────────────────────────┐
│ Backend (Python FastAPI)                                     │
│  auth / profile / signals / backtest / health                │
│  access token saved server-side only                         │
└───────────────────────────────┬──────────────────────────────┘
                                │ Kite Connect SDK
                                ▼
┌──────────────────────────────────────────────────────────────┐
│ Zerodha Kite APIs                                            │
│  session, profile, instruments, historical daily candles     │
└──────────────────────────────────────────────────────────────┘
```

Standalone CLI still exists:

- `nifty 100_sma_scanner.py` → simpler SMA-only scan → `nifty 100_sma_signals.csv`

The dashboard path is the richer research workflow.

---

## 4. Current project structure

```text
MarketResearch/
├── frontend/
│   └── src/
│       ├── pages/
│       │   ├── LoginPage.tsx
│       │   └── DashboardPage.tsx
│       ├── components/dashboard/
│       │   ├── UserTab.tsx
│       │   ├── SignalsTab.tsx          # scored signals UI
│       │   └── BacktestingTab.tsx      # historical research UI
│       ├── api/
│       │   ├── client.ts
│       │   └── types.ts
│       ├── context/AuthContext.tsx
│       └── styles/theme.css
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py                 # all tunable research defaults
│   │   ├── schemas.py
│   │   ├── routes/
│   │   │   ├── auth.py
│   │   │   ├── profile.py
│   │   │   ├── signals.py
│   │   │   └── backtest.py
│   │   └── services/
│   │       ├── kite_session.py
│   │       ├── indicators.py
│   │       ├── market_context.py
│   │       ├── signal_engine.py
│   │       ├── transaction_costs.py
│   │       ├── backtesting.py
│   │       └── sma_scanner.py
│   ├── tests/                        # pytest unit tests
│   ├── requirements.txt
│   └── .kite_session.json            # created after login (gitignored)
│
├── nifty 100_sma_scanner.py
├── nifty 100_sma_signals.csv
├── credentials.txt                   # local notes only (gitignored)
├── .env.example
├── .gitignore
├── README.md
└── PROJECT_EXPLAINED.md              # this file
```

---

## 5. Security and session handling (unchanged principle)

### Login flow

1. Open Kite login URL with your API key
2. After approval, copy one-time `request_token`
3. Enter API Key, API Secret, Request Token on the Login page
4. Frontend posts them to `POST /api/auth/login`
5. Backend calls Kite `generate_session(...)`
6. Backend stores `access_token` in memory + `backend/.kite_session.json`
7. Frontend never receives the access token

### Session reuse

On backend startup, `kite_session.try_restore()` reloads the saved token and validates it with `profile()`.

That means during local development you usually do **not** need to log in after every code reload (until the daily Kite token expires).

### Never committed

- `credentials.txt`
- `backend/.kite_session.json`
- real `.env` secrets

---

## 6. APIs (current)

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/auth/login` | Create server-side Kite session |
| `GET` | `/api/auth/status` | Is session alive / restored? |
| `POST` | `/api/auth/logout` | Clear session + delete saved token file |
| `GET` | `/api/profile` | User name, ID, products, exchanges |
| `POST` | `/api/signals/sma-crossover` | Enhanced scored Nifty scan |
| `POST` | `/api/backtest/sma` | Historical SMA backtest (+ optional combo compare) |
| `GET` | `/api/health` | Health check |

Interactive docs: http://127.0.0.1:8000/docs

### Enhanced signals request example

```json
{
  "short_sma": 6,
  "long_sma": 30,
  "lookback_days": 400,
  "max_stocks": 100,
  "rsi_period": 14,
  "volume_period": 20,
  "atr_period": 14,
  "slope_lookback": 5,
  "include_market_context": true,
  "include_sector_context": true
}
```

`max_stocks` is allowed from **1 to 200**.

Universe selection:

- `1–100` → official **Nifty 100** CSV
- `101–200` → official **Nifty 200** CSV

So if you enter `150`, the scanner loads Nifty 200 and processes the first 150 constituents (subject to successful instrument mapping / candle availability).

---

## 7. Backend modules in detail

### 7.1 `config.py`

Central place for non-secret research defaults:

- Indicator periods (SMA, RSI, ATR, volume, slope lookback)
- Slope rising/falling thresholds
- Volume strong/weak thresholds
- Extension thresholds
- ATR stop multiplier and target R-multiple
- Signal score weights and classification bands
- Approximate Indian equity transaction-cost rates + slippage bps

These are **heuristics** and should be validated with backtests before trusting them heavily.

### 7.2 `indicators.py`

Deterministic math only (no LLM):

| Function / concept | Meaning |
|--------------------|---------|
| SMA | Average close over N days |
| SMA spread % | `((short - long) / long) * 100` |
| Long SMA slope | Rising / Flat / Falling over lookback |
| Price vs long SMA | Above/below + distance % |
| Extension status | NORMAL / ELEVATED / EXTENDED vs short SMA |
| Volume metrics | Current vs average → STRONG / NORMAL / WEAK |
| RSI (Wilder) | Momentum context |
| ATR (Wilder) | Volatility estimate |
| Crossover detect | Latest bullish/bearish SMA cross |

### 7.3 `market_context.py`

- Fetches **Nifty 50** once per scan
- Classifies market as BULLISH / NEUTRAL / BEARISH using transparent rules:
  - close above long SMA + rising slope → bullish
  - close below long SMA + falling slope → bearish
  - otherwise neutral
- Sector confirmation uses a **curated symbol → sector-index map**
- If mapping is missing: `Sector confirmation unavailable` (no invented data)
- Sector/index histories are cached during one scan to reduce API calls

### 7.4 `signal_engine.py`

Builds:

1. Research risk/reward (ATR stop reference + target multiple)
2. Explainable score breakdown
3. Classification label
4. Human-readable summary

Initial score weights (sum = 100):

| Factor | Weight |
|--------|--------|
| SMA crossover | 20 |
| Price vs long SMA | 10 |
| Long SMA slope | 15 |
| Volume | 15 |
| Momentum (RSI) | 10 |
| Market context | 10 |
| Sector context | 10 |
| Overextension | 5 |
| Risk/reward structure | 5 |

Classification bands (configurable):

| Score | Strength |
|------:|----------|
| 80–100 | STRONG |
| 65–79 | GOOD |
| 50–64 | MODERATE |
| 35–49 | WEAK |
| 0–34 | AVOID / LOW CONFIDENCE |

Final labels look like `STRONG_BULLISH`, `GOOD_BEARISH`, `AVOID_BULLISH`, etc.

### 7.5 `transaction_costs.py`

Configurable approximate Indian equity cost model:

- Brokerage
- STT
- Exchange transaction charges
- SEBI charges
- Stamp duty
- GST
- Slippage in basis points

Rates must be verified against current Zerodha/NSE schedules. They are research approximations.

### 7.6 `backtesting.py`

Long-only SMA crossover backtester with explicit assumptions:

1. Crossover detected on completed day **T close**
2. Entry/exit at next session **open** (T+1 / E+1)
3. No look-ahead bias in signal detection
4. Optional costs + slippage
5. Equal capital split across selected symbols
6. Chronological train / validation / out-of-sample segment metadata

Metrics include:

- Total trades, win rate
- Average win/loss %
- Profit factor, expectancy
- Total return, CAGR (when valid)
- Max drawdown, Sharpe (approx)
- Holding period, exposure
- Costs and return before/after costs

Also supports comparing default SMA combos such as:

`5/20, 6/20, 6/30, 10/30, 10/50, 20/50, 20/100, 50/200`

Highest return is **not** automatically “best”. Prefer risk-adjusted metrics.

### 7.7 `sma_scanner.py`

Orchestrates a live research scan:

1. Download official Nifty 100 CSV
2. Map symbols → NSE EQ instrument tokens
3. Fetch daily history per stock
4. Analyze crossover + indicators
5. Attach market/sector context
6. Score and classify
7. Rank by score DESC, then crossover date DESC
8. Return scan summary + signals + optional failure reasons

One stock failing does not fail the whole scan.

---

## 8. Frontend experience (current)

### Tabs

1. **User** — Kite profile (name, ID, products, exchanges)
2. **Signals** — scored research workflow
3. **Backtesting** — historical strategy research

### Signals tab features

**Controls**

- Short SMA (default 6)
- Long SMA (default 30)
- Lookback Days
- Max Stocks (1–200, default 100)
- Advanced: RSI / Volume / ATR / slope lookback
- Advanced filters:
  - Signal type (All / Bullish / Bearish)
  - Quality (Strong / Good / Moderate / Weak)
  - Minimum score
  - Crossover age
  - Market confirmation
  - Sector confirmation
  - Volume strength
  - Sort by score / date / ticker / volume / spread / RSI / R:R

**Overview cards**

- Nifty trend
- Stocks scanned
- Bullish / Bearish counts
- Strong signals
- Average score
- New crossovers today

**Table columns**

Rank, Stock, Signal, Score, Crossover, SMA Spread, Trend, Volume, RSI, Market, Sector, R:R, Details

**Detail drawer (“View”)**

Shows full explanation:

- Score meaning
- Trend / SMA values
- Volume + RSI
- Market / sector context
- Research stop/target/R:R
- Factor-by-factor “Why this score?”
- Explicit disclaimer: research signal, not auto trade

### Backtesting tab features

- SMA periods, date range, capital
- Costs on/off, slippage bps, max stocks
- Optional SMA combo comparison
- Metrics cards
- Equity curve + drawdown chart (Recharts)
- Trades table
- Comparison table sortable by Sharpe / return / drawdown / PF / win rate

---

## 9. How to run the project

### Backend

```bash
cd backend
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

Open: http://localhost:5173

### Tests

```bash
cd backend
python -m pytest tests/ -q
```

---

## 10. How algorithmic trading fits today

Complete algo stack:

```text
Data → Signals → Decision → Risk → Execution → Reporting
```

Current project coverage:

| Stage | Status |
|-------|--------|
| Market data access | Done |
| Universe selection (Nifty 100) | Done |
| Indicator calculation | Done |
| Signal generation + scoring | Done |
| Explainability | Done |
| Historical backtesting | Done (core) |
| Transaction-cost awareness | Done (configurable) |
| Paper trading ledger | Not yet |
| Live order placement | Intentionally not implemented |
| Portfolio / risk engine automation | Not yet |

So today this is best described as:

> **Algorithmic research and decision support**

Not:

> Fully automated trading system

That is the correct order for learning and safety.

---

## 11. How to use this project to “predict” more carefully

Important: this tool does **not** predict the future with certainty.  
It helps you make **more careful, structured probability judgments**.

Use it as a research checklist, not a crystal ball.

### Step A — Start with context, not a single stock tip

Before acting on any signal, check the Signals overview:

1. Is **Nifty trend** bullish / neutral / bearish?
2. Are there many weak signals or a few strong ones?
3. What is the **average score** of the scan?

Careful rule of thumb:

- Prefer bullish stock candidates when Nifty is also supportive
- Be extra skeptical of bullish candidates when Nifty is bearish
- Treat conflicting market context as a reason to wait or size smaller

### Step B — Never trade on crossover alone

A raw crossover is only the starting event.

Prefer candidates that also show:

1. **Rising long SMA** (for bullish) or falling (for bearish)
2. **Price on the correct side** of long SMA
3. **Volume confirmation** (ideally STRONG or at least NORMAL)
4. **RSI supportive**, not extreme against your idea
5. **Market confirmation**
6. **Sector confirmation** when available
7. **Not EXTENDED** already
8. Reasonable research **R:R** (for example around 1.5–2.0+ in the framework)

Practical filter example for cautious bullish research:

```text
Signal type = Bullish
Quality = Strong or Good
Minimum score = 70+
Crossover age = Today or last 3 days
Market confirmation = Confirmed
Volume = Strong or Normal
Extension = preferably NORMAL
```

Then open the detail drawer and read the score breakdown.

### Step C — Interpret the score correctly

| Score label | Careful interpretation |
|-------------|------------------------|
| STRONG | High alignment with rules; still needs chart + risk check |
| GOOD | Decent setup; maybe wait for confirmation candle |
| MODERATE | Mixed evidence; usually watchlist only |
| WEAK | Low confidence; usually skip |
| AVOID | Do not treat as actionable research candidate |

Remember:

```text
Score 87 ≠ 87% probability of profit
```

### Step D — Use the detail drawer as a pre-trade checklist

For each candidate, ask:

1. Why did it score high? Which factors passed?
2. Which factors failed or are unknown?
3. Is price already extended?
4. Is stop reference too wide for my risk tolerance?
5. Does sector confirmation exist? If unavailable, am I okay with that uncertainty?
6. Is this a fresh crossover or already several days old?

Older crossovers are often weaker for fresh entries because part of the move may already have happened.

### Step E — Convert research into a personal decision rule (human-in-the-loop)

Example cautious personal process:

1. Generate Signals
2. Keep only `STRONG` / `GOOD` with score >= 70
3. Require market confirmation
4. Prefer volume >= NORMAL
5. Open chart manually and confirm structure (support/resistance, news risk, liquidity)
6. Define max risk in rupees before entry
7. Use ATR research stop only as a **reference**, then adjust to your own plan
8. If unclear, skip

Skipping is a valid and often superior decision.

### Step F — Validate ideas with Backtesting before trusting parameters

Do not assume SMA 6/30 is best.

In Backtesting tab:

1. Pick a multi-year date range
2. Keep costs ON
3. Use realistic slippage (for example 5–10 bps)
4. Start with a smaller `max_stocks` for speed
5. Run one SMA pair
6. Then enable **Compare SMA combos**
7. Sort by Sharpe / drawdown / profit factor, not only return

Questions to answer carefully:

- Does this SMA pair survive costs?
- Is max drawdown acceptable?
- Is win rate low but profit factor still okay (trend systems often look like this)?
- Does performance collapse out of sample?

If backtests look poor after costs, do **not** increase confidence just because today’s signal looks pretty.

### Step G — Prefer process quality over prediction confidence

A careful workflow looks like:

```text
Scan
 → Filter
 → Explain
 → Chart confirm
 → Backtest context
 → Risk size
 → Decide (trade or skip)
 → Journal result
```

An unsafe workflow looks like:

```text
See bullish badge → Buy immediately
```

### Step H — Position sizing caution (manual)

Even without an automated risk engine, use personal constraints:

- Risk only a small % of capital per idea
- Avoid clustering many correlated stocks from one weak sector
- Reduce size when market/sector confirmation is missing
- Avoid chasing EXTENDED moves

### Step I — Keep daily and intraday separate

This system is built on **daily candles**.

Do not use daily SMA 6/30 scores to micro-manage hourly entries as if they were the same strategy.  
If you later build intraday logic, it needs its own features, costs, and backtests.

---

## 12. Example: careful reading of one signal

Suppose the drawer shows:

```text
RELIANCE
STRONG BULLISH
Score 87 / 100

SMA6 crossed above SMA30 today
SMA30 rising
Price above SMA30
Volume 1.8x (STRONG)
RSI 61 (SUPPORTIVE)
Nifty BULLISH
Sector ENERGY BULLISH
Extension NORMAL
Research R:R 2.0
```

### Careful conclusion

- This is a **strong research candidate**
- Multiple independent confirmations align
- Still not a guaranteed winner
- Next human steps:
  1. Check chart levels and news
  2. Decide whether stop distance fits account risk
  3. Decide size
  4. Or wait one more day for follow-through

### Unsafe conclusion

- “Score 87, so buy with full capital now”

---

## 13. What we have achieved

1. Secure Zerodha login with server-side token storage
2. Profile integration
3. Official Nifty 100 universe loading
4. Multi-indicator research engine
5. Explainable signal scoring
6. Professional Signals dashboard with filters and detail drawer
7. Backtesting with costs, slippage, charts, and combo comparison
8. Unit tests for core math and backtest mechanics
9. Clear research wording (no “BUY NOW” automation)

---

## 14. Known limitations

- Universe:
  - Max Stocks 1–100 uses Nifty 100
  - Max Stocks 101–200 uses Nifty 200 so the requested count can actually be scanned
- Sector mapping is curated and incomplete for some symbols
- Score weights are initial heuristics, not proven optima
- Backtests use a stock subset for speed and simplify capital allocation
- No paper-trading ledger yet
- No live order execution (by design)
- Daily strategy only
- Market regimes change; historical edges can fade

---

## 15. Recommended next steps

1. Measure forward returns by score bucket (1D/3D/5D/10D/20D)
2. Validate which score factors actually improve outcomes
3. Expand/maintain sector mappings carefully
4. Add paper trading journal
5. Add risk-engine rules (max risk per trade, max correlated exposure)
6. Only then consider tightly controlled live execution

---

## 16. Glossary

| Term | Meaning |
|------|---------|
| SMA | Simple Moving Average of closes |
| Crossover | Short SMA crossing long SMA |
| Spread % | Distance between short and long SMA |
| Slope | Whether long SMA is rising/flat/falling |
| RSI | Relative Strength Index (momentum) |
| ATR | Average True Range (volatility) |
| R:R | Reward-to-risk research ratio |
| Signal score | Rule alignment score, not win probability |
| Backtest | Historical simulation under explicit assumptions |
| Slippage | Adverse fill difference vs ideal price |
| Look-ahead bias | Accidentally using future data in a test |

---

## 17. Bottom line

MarketResearch has grown from a simple SMA crossover scanner into a **professional research workstation**:

- richer evidence per signal
- explainable quality scores
- filters for careful shortlisting
- backtests to challenge assumptions
- explicit warnings against overconfidence

Use it to improve your **decision process**.

Do not use it as a substitute for risk management, judgment, or humility about uncertainty.

> Better research questions beat louder predictions.

---

## 18. Research layer and how to analyse results

Added on top of the scanner. It does not replace technical rules and it does not forecast price.

When you open a stock, the app loads:

- next earnings date and whether it is within 7 days
- a valuation flag from trailing PE (`LOW_PE`, `MID_PE`, `HIGH_PE`, `UNKNOWN`)
- a headline sentiment tag (`POSITIVE`, `NEUTRAL`, `NEGATIVE`, `UNCLEAR`)
- a decision: `RESEARCH_CANDIDATE`, `WATCH`, or `SKIP`

**Careful filter** (on by default) keeps only setups with score at least 70, aligned long-SMA slope, volume that is not weak, and extension status `NORMAL`.

### How to read a result

1. Scanner first. If it fails the careful filter, stop.
2. Open details. If sentiment is `UNCLEAR` or `NEGATIVE`, or earnings are near, the decision will say `SKIP`.
3. `RESEARCH_CANDIDATE` means the checks agree. Confirm the chart yourself and size small if you act.
4. Save a journal note. Later, record the percent result.
5. The analysis panel compares your logged outcomes: high score plus positive headlines versus high score without them.

That comparison is from your journal, not a historical news backtest. Technical backtests still live on the Backtesting tab and include costs. Do not treat one good headline, or a small sample, as proof.

---

## Disclaimer

This dashboard provides quantitative market-research signals based on historical market data and configurable trading rules. Signals, scores, stop references and targets are informational and are not guarantees of future performance or investment advice.
