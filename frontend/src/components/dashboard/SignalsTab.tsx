import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { generateSmaSignals, getJournal, getStockResearch, saveJournal } from '../../api/client'
import type { JournalAnalysis, StockResearch } from '../../api/client'
import type { SmaCrossoverResponse, SmaSignalRow } from '../../api/types'
import './SignalsTab.css'

type FormState = {
  shortSma: number
  longSma: number
  lookbackDays: number
  maxStocks: number
  rsiPeriod: number
  volumePeriod: number
  atrPeriod: number
  slopeLookback: number
}

type Filters = {
  signalType: 'ALL' | 'BULLISH' | 'BEARISH'
  quality: 'ALL' | 'STRONG' | 'GOOD' | 'MODERATE' | 'WEAK'
  minScore: number
  crossoverAge: 'ALL' | '0' | '3' | '5' | '10'
  marketConfirmed: 'ALL' | 'YES' | 'NO'
  sectorConfirmed: 'ALL' | 'YES' | 'NO'
  volume: 'ALL' | 'STRONG' | 'NORMAL' | 'WEAK'
}

type SortKey =
  | 'score'
  | 'date'
  | 'ticker'
  | 'volume'
  | 'spread'
  | 'rsi'
  | 'rr'

const DEFAULTS: FormState = {
  shortSma: 6,
  longSma: 30,
  lookbackDays: 400,
  maxStocks: 100,
  rsiPeriod: 14,
  volumePeriod: 20,
  atrPeriod: 14,
  slopeLookback: 5,
}

const DEFAULT_FILTERS: Filters = {
  signalType: 'ALL',
  quality: 'ALL',
  minScore: 0,
  crossoverAge: 'ALL',
  marketConfirmed: 'ALL',
  sectorConfirmed: 'ALL',
  volume: 'ALL',
}

function formatNumber(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return value.toLocaleString('en-IN', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

function Tip({ text }: { text: string }) {
  return (
    <span className="tip" title={text} aria-label={text}>
      i
    </span>
  )
}

function scoreClass(score: number): string {
  if (score >= 80) return 'score-high'
  if (score >= 50) return 'score-mid'
  return 'score-low'
}

function labelFromClassification(c?: string): string {
  if (!c) return '—'
  return c.replaceAll('_', ' ')
}

function passesCarefulFilter(row: SmaSignalRow): boolean {
  const score = row.signal?.score ?? 0
  const side = row.crossover?.type ?? ''
  const volume = row.volume?.confirmation ?? ''
  const extension = row.price_context?.extension_status ?? ''
  const slope = row.sma?.long_sma_direction ?? ''
  const aligned =
    (side === 'BULLISH' && slope === 'RISING') || (side === 'BEARISH' && slope === 'FALLING')
  return score >= 70 && volume !== 'WEAK' && extension === 'NORMAL' && aligned
}

function isConfirmed(side: string, trend?: string): boolean {
  if (!trend) return false
  if (side === 'BULLISH') return trend === 'BULLISH'
  if (side === 'BEARISH') return trend === 'BEARISH'
  return false
}

export function SignalsTab() {
  const [form, setForm] = useState<FormState>(DEFAULTS)
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS)
  const [sortKey, setSortKey] = useState<SortKey>('score')
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<SmaCrossoverResponse | null>(null)
  const [selected, setSelected] = useState<SmaSignalRow | null>(null)
  const [carefulOnly, setCarefulOnly] = useState(true)
  const [research, setResearch] = useState<StockResearch | null>(null)
  const [researchLoading, setResearchLoading] = useState(false)
  const [researchError, setResearchError] = useState<string | null>(null)
  const [journalNote, setJournalNote] = useState('')
  const [journalSaved, setJournalSaved] = useState<string | null>(null)
  const [analysis, setAnalysis] = useState<JournalAnalysis | null>(null)

  const filteredSorted = useMemo(() => {
    if (!result) return []
    let rows = [...result.signals]

    rows = rows.filter((row) => {
      const side = row.crossover?.type ?? ''
      const score = row.signal?.score ?? 0
      const classification = row.signal?.classification ?? ''
      const days = row.crossover?.days_since ?? 999
      const vol = row.volume?.confirmation ?? 'UNKNOWN'
      const marketOk = isConfirmed(side, row.market?.trend)
      const sectorOk = isConfirmed(side, row.sector?.trend)

      if (filters.signalType !== 'ALL' && side !== filters.signalType) return false
      if (score < filters.minScore) return false
      if (filters.quality !== 'ALL' && !classification.includes(filters.quality)) return false
      if (filters.crossoverAge !== 'ALL' && days > Number(filters.crossoverAge)) return false
      if (filters.volume !== 'ALL' && vol !== filters.volume) return false
      if (filters.marketConfirmed === 'YES' && !marketOk) return false
      if (filters.marketConfirmed === 'NO' && marketOk) return false
      if (filters.sectorConfirmed === 'YES' && !sectorOk) return false
      if (filters.sectorConfirmed === 'NO' && sectorOk) return false
      if (carefulOnly && !passesCarefulFilter(row)) return false
      return true
    })

    rows.sort((a, b) => {
      if (sortKey === 'ticker') return a.ticker.localeCompare(b.ticker)
      if (sortKey === 'date') return (b.crossover?.date ?? '').localeCompare(a.crossover?.date ?? '')
      if (sortKey === 'volume') return (b.volume?.ratio ?? 0) - (a.volume?.ratio ?? 0)
      if (sortKey === 'spread') return (b.sma?.spread_pct ?? 0) - (a.sma?.spread_pct ?? 0)
      if (sortKey === 'rsi') return (b.momentum?.rsi_14 ?? 0) - (a.momentum?.rsi_14 ?? 0)
      if (sortKey === 'rr') return (b.risk_reward?.ratio ?? 0) - (a.risk_reward?.ratio ?? 0)
      // score default
      const scoreDiff = (b.signal?.score ?? 0) - (a.signal?.score ?? 0)
      if (scoreDiff !== 0) return scoreDiff
      return (b.crossover?.date ?? '').localeCompare(a.crossover?.date ?? '')
    })

    return rows
  }, [result, filters, sortKey, carefulOnly])

  useEffect(() => {
    if (!selected) {
      setResearch(null)
      return
    }
    let cancelled = false
    setResearchLoading(true)
    setResearchError(null)
    setJournalSaved(null)
    void getStockResearch(selected.ticker, {
      score: selected.signal?.score ?? 0,
      extension: selected.price_context?.extension_status ?? 'UNKNOWN',
      volume: selected.volume?.confirmation ?? 'UNKNOWN',
      side: selected.crossover?.type ?? 'BULLISH',
      long_sma_direction: selected.sma?.long_sma_direction ?? 'UNKNOWN',
    })
      .then((data) => {
        if (!cancelled) setResearch(data)
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setResearch(null)
          setResearchError(err instanceof Error ? err.message : 'Research layer unavailable')
        }
      })
      .finally(() => {
        if (!cancelled) setResearchLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [selected])

  useEffect(() => {
    void getJournal()
      .then((data) => setAnalysis(data.analysis))
      .catch(() => setAnalysis(null))
  }, [journalSaved])

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setLoading(true)
    setSelected(null)
    try {
      const data = await generateSmaSignals({
        short_sma: form.shortSma,
        long_sma: form.longSma,
        lookback_days: form.lookbackDays,
        max_stocks: form.maxStocks,
        rsi_period: form.rsiPeriod,
        volume_period: form.volumePeriod,
        atr_period: form.atrPeriod,
        slope_lookback: form.slopeLookback,
        include_market_context: true,
        include_sector_context: true,
      })
      setResult(data)
    } catch (err) {
      setResult(null)
      setError(err instanceof Error ? err.message : 'Failed to generate signals')
    } finally {
      setLoading(false)
    }
  }

  const summary = result?.scan_summary
  const marketTrend = result?.market_context?.trend ?? '—'

  return (
    <div className="signals-tab">
      <div className="signals-hero">
        <div>
          <p className="signals-kicker">Nifty Signal Research</p>
          <h3>Quantitative crossover research — not automatic trade instructions</h3>
        </div>
      </div>

      <form className="signals-form" onSubmit={(e) => void onSubmit(e)}>
        <div className="signals-fields">
          <div className="field">
            <label htmlFor="short_sma">
              Short SMA <Tip text="Faster moving average of closing prices." />
            </label>
            <input
              id="short_sma"
              type="number"
              min={2}
              max={100}
              value={form.shortSma}
              onChange={(e) => setForm((p) => ({ ...p, shortSma: Number(e.target.value) }))}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="long_sma">
              Long SMA <Tip text="Slower moving average representing broader trend." />
            </label>
            <input
              id="long_sma"
              type="number"
              min={3}
              max={300}
              value={form.longSma}
              onChange={(e) => setForm((p) => ({ ...p, longSma: Number(e.target.value) }))}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="lookback_days">Lookback Days</label>
            <input
              id="lookback_days"
              type="number"
              min={40}
              max={2000}
              value={form.lookbackDays}
              onChange={(e) => setForm((p) => ({ ...p, lookbackDays: Number(e.target.value) }))}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="max_stocks">Max Stocks</label>
            <input
              id="max_stocks"
              type="number"
              min={1}
              max={200}
              value={form.maxStocks}
              onChange={(e) => setForm((p) => ({ ...p, maxStocks: Number(e.target.value) }))}
              required
            />
          </div>
        </div>

        <div className="signals-actions">
          <button className="btn btn-primary" type="submit" disabled={loading}>
            {loading ? 'Scanning universe…' : 'Generate Signals'}
          </button>
          <label className="careful-toggle">
            <input
              type="checkbox"
              checked={carefulOnly}
              onChange={(e) => setCarefulOnly(e.target.checked)}
            />
            Careful filter (score ≥ 70, aligned trend, strong/normal volume, not extended)
          </label>
          <button
            className="btn btn-ghost"
            type="button"
            onClick={() => setShowAdvanced((v) => !v)}
          >
            {showAdvanced ? 'Hide Advanced Filters' : 'Advanced Filters'}
          </button>
          <p className="signals-hint muted">
            Strategy: SMA {form.shortSma}/{form.longSma} · RSI {form.rsiPeriod} · Volume{' '}
            {form.volumePeriod} · ATR {form.atrPeriod}. Max Stocks {form.maxStocks} uses{' '}
            {form.maxStocks > 100 ? 'Nifty 200' : 'Nifty 100'} constituents.
          </p>
        </div>

        {showAdvanced ? (
          <div className="signals-advanced">
            <div className="signals-fields">
              <div className="field">
                <label htmlFor="rsi_period">RSI Period</label>
                <input
                  id="rsi_period"
                  type="number"
                  min={2}
                  value={form.rsiPeriod}
                  onChange={(e) => setForm((p) => ({ ...p, rsiPeriod: Number(e.target.value) }))}
                />
              </div>
              <div className="field">
                <label htmlFor="volume_period">Volume Period</label>
                <input
                  id="volume_period"
                  type="number"
                  min={2}
                  value={form.volumePeriod}
                  onChange={(e) =>
                    setForm((p) => ({ ...p, volumePeriod: Number(e.target.value) }))
                  }
                />
              </div>
              <div className="field">
                <label htmlFor="atr_period">ATR Period</label>
                <input
                  id="atr_period"
                  type="number"
                  min={2}
                  value={form.atrPeriod}
                  onChange={(e) => setForm((p) => ({ ...p, atrPeriod: Number(e.target.value) }))}
                />
              </div>
              <div className="field">
                <label htmlFor="slope_lookback">SMA Slope Lookback</label>
                <input
                  id="slope_lookback"
                  type="number"
                  min={1}
                  value={form.slopeLookback}
                  onChange={(e) =>
                    setForm((p) => ({ ...p, slopeLookback: Number(e.target.value) }))
                  }
                />
              </div>
            </div>

            <div className="signals-fields filters-grid">
              <div className="field">
                <label htmlFor="filter_type">Signal Type</label>
                <select
                  id="filter_type"
                  value={filters.signalType}
                  onChange={(e) =>
                    setFilters((p) => ({
                      ...p,
                      signalType: e.target.value as Filters['signalType'],
                    }))
                  }
                >
                  <option value="ALL">All</option>
                  <option value="BULLISH">Bullish</option>
                  <option value="BEARISH">Bearish</option>
                </select>
              </div>
              <div className="field">
                <label htmlFor="filter_quality">Signal Quality</label>
                <select
                  id="filter_quality"
                  value={filters.quality}
                  onChange={(e) =>
                    setFilters((p) => ({ ...p, quality: e.target.value as Filters['quality'] }))
                  }
                >
                  <option value="ALL">All</option>
                  <option value="STRONG">Strong</option>
                  <option value="GOOD">Good</option>
                  <option value="MODERATE">Moderate</option>
                  <option value="WEAK">Weak</option>
                </select>
              </div>
              <div className="field">
                <label htmlFor="filter_score">Minimum Score</label>
                <input
                  id="filter_score"
                  type="number"
                  min={0}
                  max={100}
                  value={filters.minScore}
                  onChange={(e) => setFilters((p) => ({ ...p, minScore: Number(e.target.value) }))}
                />
              </div>
              <div className="field">
                <label htmlFor="filter_age">Crossover Age</label>
                <select
                  id="filter_age"
                  value={filters.crossoverAge}
                  onChange={(e) =>
                    setFilters((p) => ({
                      ...p,
                      crossoverAge: e.target.value as Filters['crossoverAge'],
                    }))
                  }
                >
                  <option value="ALL">All</option>
                  <option value="0">Today</option>
                  <option value="3">Last 3 days</option>
                  <option value="5">Last 5 days</option>
                  <option value="10">Last 10 days</option>
                </select>
              </div>
              <div className="field">
                <label htmlFor="filter_market">Market Confirmation</label>
                <select
                  id="filter_market"
                  value={filters.marketConfirmed}
                  onChange={(e) =>
                    setFilters((p) => ({
                      ...p,
                      marketConfirmed: e.target.value as Filters['marketConfirmed'],
                    }))
                  }
                >
                  <option value="ALL">All</option>
                  <option value="YES">Confirmed</option>
                  <option value="NO">Not Confirmed</option>
                </select>
              </div>
              <div className="field">
                <label htmlFor="filter_sector">Sector Confirmation</label>
                <select
                  id="filter_sector"
                  value={filters.sectorConfirmed}
                  onChange={(e) =>
                    setFilters((p) => ({
                      ...p,
                      sectorConfirmed: e.target.value as Filters['sectorConfirmed'],
                    }))
                  }
                >
                  <option value="ALL">All</option>
                  <option value="YES">Confirmed</option>
                  <option value="NO">Not Confirmed</option>
                </select>
              </div>
              <div className="field">
                <label htmlFor="filter_vol">Volume</label>
                <select
                  id="filter_vol"
                  value={filters.volume}
                  onChange={(e) =>
                    setFilters((p) => ({ ...p, volume: e.target.value as Filters['volume'] }))
                  }
                >
                  <option value="ALL">All</option>
                  <option value="STRONG">Strong</option>
                  <option value="NORMAL">Normal</option>
                  <option value="WEAK">Weak</option>
                </select>
              </div>
              <div className="field">
                <label htmlFor="sort_key">Sort By</label>
                <select
                  id="sort_key"
                  value={sortKey}
                  onChange={(e) => setSortKey(e.target.value as SortKey)}
                >
                  <option value="score">Signal Score</option>
                  <option value="date">Most Recent Crossover</option>
                  <option value="ticker">Ticker</option>
                  <option value="volume">Volume Strength</option>
                  <option value="spread">SMA Spread</option>
                  <option value="rsi">RSI</option>
                  <option value="rr">Risk/Reward</option>
                </select>
              </div>
            </div>
          </div>
        ) : null}
      </form>

      {error ? <div className="alert alert-error">{error}</div> : null}

      {loading ? (
        <div className="signals-loading">
          <div className="signals-spinner" aria-hidden="true" />
          <p>Fetching candles, indicators, market/sector context and scoring signals…</p>
        </div>
      ) : null}

      {result && !loading ? (
        <>
          <div className="overview-grid">
            <div className="overview-card">
              <span>Universe</span>
              <strong>{summary?.universe ?? (form.maxStocks > 100 ? 'NIFTY 200' : 'NIFTY 100')}</strong>
            </div>
            <div className="overview-card">
              <span>Nifty Trend</span>
              <strong>{marketTrend}</strong>
            </div>
            <div className="overview-card">
              <span>Stocks Requested</span>
              <strong>{summary?.stocks_requested ?? result.max_stocks}</strong>
            </div>
            <div className="overview-card">
              <span>Stocks Scanned</span>
              <strong>{summary?.stocks_scanned ?? result.scanned}</strong>
            </div>
            <div className="overview-card">
              <span>Bullish</span>
              <strong className="bullish">{summary?.bullish ?? 0}</strong>
            </div>
            <div className="overview-card">
              <span>Bearish</span>
              <strong className="bearish">{summary?.bearish ?? 0}</strong>
            </div>
            <div className="overview-card">
              <span>Strong Signals</span>
              <strong>{summary?.strong_signals ?? 0}</strong>
            </div>
            <div className="overview-card">
              <span>Avg Score</span>
              <strong>{formatNumber(summary?.average_score ?? 0, 1)}</strong>
            </div>
          </div>

          <div className="summary-cards">
            <div className="mini-card">
              <span>Strong Bullish</span>
              <strong>
                {
                  result.signals.filter((s) => s.signal?.classification === 'STRONG_BULLISH')
                    .length
                }
              </strong>
            </div>
            <div className="mini-card">
              <span>Strong Bearish</span>
              <strong>
                {
                  result.signals.filter((s) => s.signal?.classification === 'STRONG_BEARISH')
                    .length
                }
              </strong>
            </div>
            <div className="mini-card">
              <span>New Crossovers Today</span>
              <strong>
                {result.signals.filter((s) => (s.crossover?.days_since ?? 99) === 0).length}
              </strong>
            </div>
            <div className="mini-card">
              <span>Market Trend</span>
              <strong>{marketTrend}</strong>
            </div>
          </div>

          {filteredSorted.length === 0 ? (
            <div className="signals-empty muted">No signals match the current filters.</div>
          ) : (
            <div className="signals-table-wrap">
              <table className="signals-table">
                <thead>
                  <tr>
                    <th>Rank</th>
                    <th>Stock</th>
                    <th>
                      Signal <Tip text="Research classification from the configured score rules." />
                    </th>
                    <th>
                      Score <Tip text="0–100 rule-based research score. Not a probability." />
                    </th>
                    <th>Crossover</th>
                    <th>
                      SMA Spread <Tip text="((short SMA − long SMA) / long SMA) × 100." />
                    </th>
                    <th>
                      Trend <Tip text="Direction of the long SMA over the slope lookback." />
                    </th>
                    <th>
                      Volume <Tip text="Current volume vs recent average." />
                    </th>
                    <th>
                      RSI <Tip text="Wilder RSI momentum context." />
                    </th>
                    <th>Market</th>
                    <th>Sector</th>
                    <th>
                      R:R <Tip text="Hypothetical research reward/risk using ATR stop framework." />
                    </th>
                    <th>Details</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredSorted.map((row, idx) => {
                    const score = row.signal?.score ?? 0
                    const side = row.crossover?.type ?? ''
                    const spread = row.sma?.spread_pct
                    return (
                      <tr key={`${row.ticker}-${row.crossover?.date ?? idx}`}>
                        <td className="mono">{idx + 1}</td>
                        <td>
                          <div className="stock-cell">
                            <span className="mono ticker">{row.ticker}</span>
                            <span className="muted company">{row.company}</span>
                          </div>
                        </td>
                        <td>
                          <span
                            className={`signal-badge ${
                              side === 'BULLISH' ? 'is-bullish' : 'is-bearish'
                            }`}
                          >
                            {labelFromClassification(row.signal?.classification)}
                          </span>
                        </td>
                        <td>
                          <div className={`score-pill ${scoreClass(score)}`}>
                            <span>{score}</span>
                            <div className="score-bar">
                              <div style={{ width: `${score}%` }} />
                            </div>
                          </div>
                        </td>
                        <td className="mono">
                          {row.crossover?.days_since === 0
                            ? 'Today'
                            : row.crossover?.date ?? '—'}
                        </td>
                        <td className="mono">
                          {spread === null || spread === undefined
                            ? '—'
                            : `${spread > 0 ? '+' : ''}${formatNumber(spread)}%`}
                        </td>
                        <td>{row.sma?.long_sma_direction ?? '—'}</td>
                        <td className="mono">
                          {row.volume?.ratio ? `${formatNumber(row.volume.ratio, 1)}x` : '—'}
                        </td>
                        <td className="mono">{formatNumber(row.momentum?.rsi_14, 1)}</td>
                        <td>
                          {isConfirmed(side, row.market?.trend) ? 'Confirmed' : row.market?.trend ?? '—'}
                        </td>
                        <td>
                          {row.sector?.available === false
                            ? 'Unavailable'
                            : isConfirmed(side, row.sector?.trend)
                              ? 'Confirmed'
                              : row.sector?.trend ?? '—'}
                        </td>
                        <td className="mono">{formatNumber(row.risk_reward?.ratio, 1)}</td>
                        <td>
                          <button
                            type="button"
                            className="btn btn-ghost btn-tiny"
                            onClick={() => setSelected(row)}
                          >
                            View
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}

          <p className="disclaimer muted">
            {result.disclaimer ??
              'This dashboard provides quantitative market-research signals based on historical market data and configurable trading rules. Signals, scores, stop references and targets are informational and are not guarantees of future performance or investment advice.'}
          </p>

          <section className="analysis-panel">
            <h3>How to analyse results</h3>
            <ol>
              <li>Use the scanner as the first filter: score, trend, volume, and not extended.</li>
              <li>Open a stock and read earnings, valuation flag, and headline sentiment.</li>
              <li>If the decision says SKIP or sentiment is UNCLEAR, skip it.</li>
              <li>Journal the idea, then later record the percent result.</li>
              <li>Compare high-score + positive sentiment against high-score without it. Trust the comparison only after many samples.</li>
            </ol>
            <div className="analysis-stats">
              <div>
                <span>Journaled outcomes</span>
                <strong>{analysis?.logged_with_outcome ?? 0}</strong>
              </div>
              <div>
                <span>Score ≥ 70 + positive news</span>
                <strong>
                  {analysis?.high_score_positive_avg_return == null
                    ? 'N/A'
                    : `${analysis.high_score_positive_avg_return}% (${analysis.high_score_positive_count})`}
                </strong>
              </div>
              <div>
                <span>Score ≥ 70 without positive news</span>
                <strong>
                  {analysis?.high_score_other_avg_return == null
                    ? 'N/A'
                    : `${analysis.high_score_other_avg_return}% (${analysis.high_score_other_count})`}
                </strong>
              </div>
            </div>
            <p className="muted small">
              {analysis?.how_to_read ??
                'Backtests cover technical rules and costs. News sentiment is current context, so it is measured from your journal, not invented historically.'}
            </p>
          </section>
        </>
      ) : null}

      {selected ? (
        <div className="drawer-backdrop" onClick={() => setSelected(null)} role="presentation">
          <aside
            className="drawer"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-label={`${selected.ticker} signal details`}
          >
            <div className="drawer-head">
              <div>
                <p className="signals-kicker">{selected.ticker}</p>
                <h3>{labelFromClassification(selected.signal?.classification)}</h3>
                <p className="muted">{selected.company}</p>
              </div>
              <button type="button" className="btn btn-ghost" onClick={() => setSelected(null)}>
                Close
              </button>
            </div>

            <div className={`drawer-score ${scoreClass(selected.signal?.score ?? 0)}`}>
              <span>Signal Quality</span>
              <strong>
                {selected.signal?.score ?? 0} / 100
              </strong>
              <div className="score-bar large">
                <div style={{ width: `${selected.signal?.score ?? 0}%` }} />
              </div>
              <p className="muted small">
                Score means alignment with configured research rules — not probability of profit.
              </p>
            </div>

            <section className="drawer-section">
              <h4>Trend</h4>
              <dl>
                <dt>SMA {selected.sma?.short_period}</dt>
                <dd>₹{formatNumber(selected.sma?.short_value)}</dd>
                <dt>SMA {selected.sma?.long_period}</dt>
                <dd>₹{formatNumber(selected.sma?.long_value)}</dd>
                <dt>Spread</dt>
                <dd>
                  {selected.sma?.spread_pct == null
                    ? '—'
                    : `${selected.sma.spread_pct > 0 ? '+' : ''}${formatNumber(selected.sma.spread_pct)}%`}
                </dd>
                <dt>Long SMA Trend</dt>
                <dd>{selected.sma?.long_sma_direction}</dd>
              </dl>
            </section>

            <section className="drawer-section">
              <h4>Volume & Momentum</h4>
              <dl>
                <dt>Volume Ratio</dt>
                <dd>
                  {selected.volume?.ratio ? `${formatNumber(selected.volume.ratio, 2)}x` : '—'} (
                  {selected.volume?.confirmation})
                </dd>
                <dt>RSI14</dt>
                <dd>
                  {formatNumber(selected.momentum?.rsi_14, 1)} ({selected.momentum?.status})
                </dd>
              </dl>
            </section>

            <section className="drawer-section">
              <h4>Context</h4>
              <dl>
                <dt>Nifty</dt>
                <dd>{selected.market?.trend}</dd>
                <dt>Sector</dt>
                <dd>
                  {selected.sector?.name ?? '—'} · {selected.sector?.trend}
                </dd>
                <dt>Extension</dt>
                <dd>{selected.price_context?.extension_status}</dd>
              </dl>
            </section>

            <section className="drawer-section">
              <h4>Risk Research</h4>
              <p className="muted small">Research stop reference — not a guaranteed stop loss.</p>
              <dl>
                <dt>ATR14</dt>
                <dd>₹{formatNumber(selected.volatility?.atr_14)}</dd>
                <dt>Entry ref</dt>
                <dd>₹{formatNumber(selected.risk_reward?.entry_reference)}</dd>
                <dt>Stop ref</dt>
                <dd>₹{formatNumber(selected.risk_reward?.stop_reference)}</dd>
                <dt>Target ref</dt>
                <dd>₹{formatNumber(selected.risk_reward?.target_reference)}</dd>
                <dt>R:R</dt>
                <dd>{formatNumber(selected.risk_reward?.ratio, 2)}</dd>
              </dl>
            </section>

            <section className="drawer-section">
              <h4>Research layer</h4>
              {researchLoading ? <p className="muted small">Loading earnings, valuation, and headlines…</p> : null}
              {researchError ? <div className="alert alert-error">{researchError}</div> : null}
              {research ? (
                <>
                  <dl>
                    <dt>Decision</dt>
                    <dd>{research.decision.action.replaceAll('_', ' ')}</dd>
                    <dt>Sentiment</dt>
                    <dd>{research.sentiment.tag}</dd>
                    <dt>Valuation</dt>
                    <dd>
                      {research.valuation.flag}
                      {research.valuation.pe != null ? ` · PE ${research.valuation.pe}` : ''}
                    </dd>
                    <dt>Earnings</dt>
                    <dd>
                      {research.earnings.date ?? 'Unknown'} · {research.earnings.event_risk}
                    </dd>
                  </dl>
                  <p className="muted small">{research.decision.size_hint}</p>
                  <ul className="breakdown-list">
                    {research.decision.reasons.map((reason) => (
                      <li key={reason}>{reason}</li>
                    ))}
                  </ul>
                  {research.sentiment.headlines.length ? (
                    <ul className="headline-list">
                      {research.sentiment.headlines.map((title) => (
                        <li key={title}>{title}</li>
                      ))}
                    </ul>
                  ) : null}
                  <form
                    className="journal-form"
                    onSubmit={(event) => {
                      event.preventDefault()
                      void saveJournal({
                        ticker: selected.ticker,
                        score: selected.signal?.score ?? 0,
                        classification: selected.signal?.classification,
                        sentiment: research.sentiment.tag,
                        valuation_flag: research.valuation.flag,
                        decision: research.decision.action,
                        notes: journalNote,
                      }).then(() => {
                        setJournalSaved(new Date().toISOString())
                        setJournalNote('')
                      })
                    }}
                  >
                    <label htmlFor="journal_note">Journal note</label>
                    <input
                      id="journal_note"
                      value={journalNote}
                      onChange={(e) => setJournalNote(e.target.value)}
                      placeholder="Why you would take or skip this"
                    />
                    <button className="btn btn-ghost" type="submit">
                      Save to journal
                    </button>
                    {journalSaved ? <p className="muted small">Saved. Record the % result later to measure it.</p> : null}
                  </form>
                </>
              ) : null}
            </section>

            <section className="drawer-section">
              <h4>Why this score?</h4>
              <ul className="breakdown-list">
                {(selected.score_breakdown ?? []).map((item) => (
                  <li key={item.factor}>
                    <span className={`status-dot status-${item.status.toLowerCase()}`} />
                    <div>
                      <strong>
                        {item.factor} ({formatNumber(item.score, 1)}/{item.max_score})
                      </strong>
                      <p className="muted small">{item.reason}</p>
                    </div>
                  </li>
                ))}
              </ul>
            </section>

            <p className="drawer-summary">{selected.signal?.summary}</p>
            <p className="disclaimer muted">
              This is a research signal, not an automatic trade instruction or investment advice.
            </p>
          </aside>
        </div>
      ) : null}
    </div>
  )
}
