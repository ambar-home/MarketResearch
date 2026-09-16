import { useMemo, useState, type FormEvent } from 'react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { runSmaBacktest } from '../../api/client'
import type { BacktestResponse } from '../../api/types'
import './BacktestingTab.css'

type FormState = {
  shortSma: number
  longSma: number
  startDate: string
  endDate: string
  initialCapital: number
  transactionCosts: boolean
  slippageBps: number
  maxStocks: number
  compareCombos: boolean
}

const DEFAULTS: FormState = {
  shortSma: 6,
  longSma: 30,
  startDate: '2023-01-01',
  endDate: '2025-12-31',
  initialCapital: 1_000_000,
  transactionCosts: true,
  slippageBps: 5,
  maxStocks: 10,
  compareCombos: false,
}

function fmt(value: number | string | null | undefined, digits = 2): string {
  if (value === null || value === undefined || value === '') return 'N/A'
  if (typeof value === 'string') return value
  return value.toLocaleString('en-IN', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

export function BacktestingTab() {
  const [form, setForm] = useState<FormState>(DEFAULTS)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<BacktestResponse | null>(null)
  const [compareSort, setCompareSort] = useState<string>('sharpe_ratio')

  const comparisons = useMemo(() => {
    const rows = [...(result?.comparisons ?? [])]
    rows.sort((a, b) => {
      const av = Number(a[compareSort] ?? Number.NEGATIVE_INFINITY)
      const bv = Number(b[compareSort] ?? Number.NEGATIVE_INFINITY)
      return bv - av
    })
    return rows
  }, [result, compareSort])

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const data = await runSmaBacktest({
        short_sma: form.shortSma,
        long_sma: form.longSma,
        start_date: form.startDate,
        end_date: form.endDate,
        initial_capital: form.initialCapital,
        transaction_costs: form.transactionCosts,
        slippage_bps: form.slippageBps,
        max_stocks: form.maxStocks,
        compare_combos: form.compareCombos,
      })
      setResult(data)
    } catch (err) {
      setResult(null)
      setError(err instanceof Error ? err.message : 'Backtest failed')
    } finally {
      setLoading(false)
    }
  }

  const metrics = result?.metrics

  return (
    <div className="backtest-tab">
      <div className="backtest-hero">
        <p className="backtest-kicker">Historical Strategy Research</p>
        <h3>SMA crossover backtesting with costs, slippage and chronological segments</h3>
        <p className="muted">
          Hypothetical research only. Past performance does not guarantee future results. No live
          orders are placed.
        </p>
      </div>

      <form className="backtest-form" onSubmit={(e) => void onSubmit(e)}>
        <div className="backtest-fields">
          <div className="field">
            <label htmlFor="bt_short">Short SMA</label>
            <input
              id="bt_short"
              type="number"
              min={2}
              value={form.shortSma}
              onChange={(e) => setForm((p) => ({ ...p, shortSma: Number(e.target.value) }))}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="bt_long">Long SMA</label>
            <input
              id="bt_long"
              type="number"
              min={3}
              value={form.longSma}
              onChange={(e) => setForm((p) => ({ ...p, longSma: Number(e.target.value) }))}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="bt_start">Start Date</label>
            <input
              id="bt_start"
              type="date"
              value={form.startDate}
              onChange={(e) => setForm((p) => ({ ...p, startDate: e.target.value }))}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="bt_end">End Date</label>
            <input
              id="bt_end"
              type="date"
              value={form.endDate}
              onChange={(e) => setForm((p) => ({ ...p, endDate: e.target.value }))}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="bt_capital">Initial Capital</label>
            <input
              id="bt_capital"
              type="number"
              min={1000}
              value={form.initialCapital}
              onChange={(e) => setForm((p) => ({ ...p, initialCapital: Number(e.target.value) }))}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="bt_slip">Slippage (bps)</label>
            <input
              id="bt_slip"
              type="number"
              min={0}
              value={form.slippageBps}
              onChange={(e) => setForm((p) => ({ ...p, slippageBps: Number(e.target.value) }))}
            />
          </div>
          <div className="field">
            <label htmlFor="bt_max">Max Stocks</label>
            <input
              id="bt_max"
              type="number"
              min={1}
              max={200}
              value={form.maxStocks}
              onChange={(e) => setForm((p) => ({ ...p, maxStocks: Number(e.target.value) }))}
            />
          </div>
          <div className="field checkbox-field">
            <label htmlFor="bt_costs">
              <input
                id="bt_costs"
                type="checkbox"
                checked={form.transactionCosts}
                onChange={(e) => setForm((p) => ({ ...p, transactionCosts: e.target.checked }))}
              />
              Transaction costs on
            </label>
            <label htmlFor="bt_compare">
              <input
                id="bt_compare"
                type="checkbox"
                checked={form.compareCombos}
                onChange={(e) => setForm((p) => ({ ...p, compareCombos: e.target.checked }))}
              />
              Compare SMA combos
            </label>
          </div>
        </div>

        <button className="btn btn-primary" type="submit" disabled={loading}>
          {loading ? 'Running backtest…' : 'Run Backtest'}
        </button>
        <p className="muted small">
          Uses a subset of Nifty 100 for speed. Full-universe research runs can take several minutes.
        </p>
      </form>

      {error ? <div className="alert alert-error">{error}</div> : null}

      {result && !loading ? (
        <>
          <div className="metric-grid">
            <div className="metric-card">
              <span>Total Return</span>
              <strong>{fmt(metrics?.total_return_pct)}%</strong>
            </div>
            <div className="metric-card">
              <span>CAGR</span>
              <strong>{fmt(metrics?.cagr_pct)}%</strong>
            </div>
            <div className="metric-card">
              <span>Win Rate</span>
              <strong>{fmt(metrics?.win_rate)}%</strong>
            </div>
            <div className="metric-card">
              <span>Max Drawdown</span>
              <strong>{fmt(metrics?.max_drawdown_pct)}%</strong>
            </div>
            <div className="metric-card">
              <span>Profit Factor</span>
              <strong>{fmt(metrics?.profit_factor, 3)}</strong>
            </div>
            <div className="metric-card">
              <span>Sharpe</span>
              <strong>{fmt(metrics?.sharpe_ratio, 3)}</strong>
            </div>
            <div className="metric-card">
              <span>Trades</span>
              <strong>{fmt(metrics?.total_trades, 0)}</strong>
            </div>
            <div className="metric-card">
              <span>Costs</span>
              <strong>₹{fmt(metrics?.transaction_costs)}</strong>
            </div>
          </div>

          <div className="chart-panel">
            <h4>Equity Curve</h4>
            <div className="chart-box">
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={result.equity_curve}>
                  <CartesianGrid stroke="rgba(148,163,184,0.15)" />
                  <XAxis dataKey="date" hide />
                  <YAxis stroke="#94a3b8" width={70} />
                  <Tooltip />
                  <Line type="monotone" dataKey="equity" stroke="#2dd4bf" dot={false} strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="chart-panel">
            <h4>Drawdown Curve</h4>
            <div className="chart-box">
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={result.drawdown_curve}>
                  <CartesianGrid stroke="rgba(148,163,184,0.15)" />
                  <XAxis dataKey="date" hide />
                  <YAxis stroke="#94a3b8" width={50} />
                  <Tooltip />
                  <Line
                    type="monotone"
                    dataKey="drawdown_pct"
                    stroke="#f87171"
                    dot={false}
                    strokeWidth={2}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="assumptions">
            <h4>Execution assumptions</h4>
            <ul>
              {result.execution_assumptions.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>

          {comparisons.length ? (
            <div className="compare-block">
              <div className="compare-head">
                <h4>Strategy Comparison</h4>
                <select value={compareSort} onChange={(e) => setCompareSort(e.target.value)}>
                  <option value="sharpe_ratio">Sharpe</option>
                  <option value="total_return_pct">Return</option>
                  <option value="max_drawdown_pct">Drawdown</option>
                  <option value="profit_factor">Profit Factor</option>
                  <option value="win_rate">Win Rate</option>
                </select>
              </div>
              <p className="muted small">{result.comparison_note}</p>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Strategy</th>
                      <th>Return</th>
                      <th>Drawdown</th>
                      <th>Win Rate</th>
                      <th>PF</th>
                      <th>Sharpe</th>
                      <th>Trades</th>
                    </tr>
                  </thead>
                  <tbody>
                    {comparisons.map((row) => (
                      <tr key={String(row.strategy)}>
                        <td className="mono">{String(row.strategy)}</td>
                        <td>{fmt(row.total_return_pct as number)}%</td>
                        <td>{fmt(row.max_drawdown_pct as number)}%</td>
                        <td>{fmt(row.win_rate as number)}%</td>
                        <td>{fmt(row.profit_factor as number, 3)}</td>
                        <td>{fmt(row.sharpe_ratio as number, 3)}</td>
                        <td>{fmt(row.total_trades as number, 0)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : null}

          <div className="table-wrap">
            <h4>Trades</h4>
            <table>
              <thead>
                <tr>
                  <th>Ticker</th>
                  <th>Entry</th>
                  <th>Exit</th>
                  <th>Entry Px</th>
                  <th>Exit Px</th>
                  <th>Return %</th>
                  <th>PnL</th>
                  <th>Days</th>
                  <th>Costs</th>
                </tr>
              </thead>
              <tbody>
                {result.trades.slice(0, 100).map((t, i) => (
                  <tr key={`${String(t.ticker)}-${String(t.entry_date)}-${i}`}>
                    <td className="mono">{String(t.ticker)}</td>
                    <td className="mono">{String(t.entry_date)}</td>
                    <td className="mono">{String(t.exit_date)}</td>
                    <td>{fmt(t.entry_price as number)}</td>
                    <td>{fmt(t.exit_price as number)}</td>
                    <td>{fmt(t.return_pct as number)}%</td>
                    <td>{fmt(t.pnl as number)}</td>
                    <td>{fmt(t.holding_days as number, 0)}</td>
                    <td>{fmt(t.costs as number)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p className="disclaimer muted">{result.disclaimer}</p>
        </>
      ) : null}
    </div>
  )
}
