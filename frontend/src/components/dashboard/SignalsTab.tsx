import { useMemo, useState, type FormEvent } from 'react'
import { generateSmaSignals } from '../../api/client'
import type { SmaCrossoverResponse, SmaSignalRow } from '../../api/types'
import './SignalsTab.css'

type FormState = {
  shortSma: number
  longSma: number
  lookbackDays: number
  maxStocks: number
}

const DEFAULTS: FormState = {
  shortSma: 6,
  longSma: 30,
  lookbackDays: 400,
  maxStocks: 100,
}

function formatNumber(value: number): string {
  return value.toLocaleString('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

export function SignalsTab() {
  const [form, setForm] = useState<FormState>(DEFAULTS)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<SmaCrossoverResponse | null>(null)

  const summary = useMemo(() => {
    if (!result) return null
    const bullish = result.signals.filter((s) => s.crossover_type === 'Bullish').length
    const bearish = result.signals.filter((s) => s.crossover_type === 'Bearish').length
    return { bullish, bearish }
  }, [result])

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setLoading(true)

    try {
      const data = await generateSmaSignals({
        short_sma: form.shortSma,
        long_sma: form.longSma,
        lookback_days: form.lookbackDays,
        max_stocks: form.maxStocks,
      })
      setResult(data)
    } catch (err) {
      setResult(null)
      setError(err instanceof Error ? err.message : 'Failed to generate signals')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="signals-tab">
      <form className="signals-form" onSubmit={(e) => void onSubmit(e)}>
        <div className="signals-fields">
          <div className="field">
            <label htmlFor="short_sma">Short SMA</label>
            <input
              id="short_sma"
              type="number"
              min={2}
              max={100}
              value={form.shortSma}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, shortSma: Number(e.target.value) }))
              }
              required
            />
          </div>

          <div className="field">
            <label htmlFor="long_sma">Long SMA</label>
            <input
              id="long_sma"
              type="number"
              min={3}
              max={300}
              value={form.longSma}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, longSma: Number(e.target.value) }))
              }
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
              onChange={(e) =>
                setForm((prev) => ({ ...prev, lookbackDays: Number(e.target.value) }))
              }
              required
            />
          </div>

          <div className="field">
            <label htmlFor="max_stocks">Max Stocks</label>
            <input
              id="max_stocks"
              type="number"
              min={1}
              max={100}
              value={form.maxStocks}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, maxStocks: Number(e.target.value) }))
              }
              required
            />
          </div>
        </div>

        <div className="signals-actions">
          <button className="btn btn-primary" type="submit" disabled={loading}>
            {loading ? 'Scanning Nifty 100…' : 'Generate Signals'}
          </button>
          <p className="signals-hint muted">
            Uses official Nifty 100 constituents and your saved Kite session. A full scan
            can take a minute or two.
          </p>
        </div>
      </form>

      {error ? <div className="alert alert-error">{error}</div> : null}

      {loading ? (
        <div className="signals-loading">
          <div className="signals-spinner" aria-hidden="true" />
          <p>Fetching daily candles and detecting SMA crossovers…</p>
        </div>
      ) : null}

      {result && !loading ? (
        <div className="signals-results">
          <div className="signals-summary">
            <div>
              <span className="signals-stat-label">Signals</span>
              <strong>{result.signals_found}</strong>
            </div>
            <div>
              <span className="signals-stat-label">Scanned</span>
              <strong>{result.scanned}</strong>
            </div>
            <div>
              <span className="signals-stat-label">Bullish</span>
              <strong className="bullish">{summary?.bullish ?? 0}</strong>
            </div>
            <div>
              <span className="signals-stat-label">Bearish</span>
              <strong className="bearish">{summary?.bearish ?? 0}</strong>
            </div>
          </div>

          {result.signals.length === 0 ? (
            <div className="signals-empty muted">
              No crossovers found in the lookback window for the selected settings.
            </div>
          ) : (
            <div className="signals-table-wrap">
              <table className="signals-table">
                <thead>
                  <tr>
                    <th>Rank</th>
                    <th>Ticker</th>
                    <th>Company</th>
                    <th>Crossover Type</th>
                    <th>Crossover Date</th>
                    <th>Close</th>
                    <th>SMA {result.short_sma}</th>
                    <th>SMA {result.long_sma}</th>
                  </tr>
                </thead>
                <tbody>
                  {result.signals.map((row: SmaSignalRow) => (
                    <tr key={`${row.ticker}-${row.crossover_date}`}>
                      <td className="mono">{row.rank}</td>
                      <td className="mono ticker">{row.ticker}</td>
                      <td>{row.company}</td>
                      <td>
                        <span
                          className={`signal-badge ${
                            row.crossover_type === 'Bullish' ? 'is-bullish' : 'is-bearish'
                          }`}
                        >
                          {row.crossover_type}
                        </span>
                      </td>
                      <td className="mono">{row.crossover_date}</td>
                      <td className="mono num">{formatNumber(row.close)}</td>
                      <td className="mono num">{formatNumber(row.sma_short)}</td>
                      <td className="mono num">{formatNumber(row.sma_long)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : null}
    </div>
  )
}
