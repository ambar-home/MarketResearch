import { useEffect, useState } from 'react'
import { getPortfolio, type Portfolio } from '../../api/client'
import './PortfolioTab.css'

function money(value: number): string {
  return value.toLocaleString('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

function signedClass(value: number): string {
  if (value > 0) return 'is-up'
  if (value < 0) return 'is-down'
  return ''
}

export function PortfolioTab() {
  const [data, setData] = useState<Portfolio | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const next = await getPortfolio()
        if (!cancelled) setData(next)
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Could not load portfolio')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [])

  if (loading) return <p className="muted">Loading Zerodha portfolio…</p>
  if (error) return <div className="alert alert-error">{error}</div>
  if (!data) return <p className="muted">No portfolio data.</p>

  const summary = data.summary

  return (
    <div className="portfolio-tab">
      <div className="portfolio-summary">
        <div>
          <span>Invested</span>
          <strong>₹{money(summary.invested_value)}</strong>
        </div>
        <div>
          <span>Current value</span>
          <strong>₹{money(summary.current_value)}</strong>
        </div>
        <div>
          <span>Total P&L</span>
          <strong className={signedClass(summary.pnl)}>
            ₹{money(summary.pnl)} ({money(summary.pnl_pct)}%)
          </strong>
        </div>
        <div>
          <span>Day P&L</span>
          <strong className={signedClass(summary.day_pnl)}>₹{money(summary.day_pnl)}</strong>
        </div>
      </div>

      <section>
        <h3>Holdings ({summary.holdings_count})</h3>
        {data.holdings.length === 0 ? (
          <p className="muted">No equity holdings in this Zerodha account.</p>
        ) : (
          <div className="portfolio-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Qty</th>
                  <th>Avg</th>
                  <th>LTP</th>
                  <th>Invested</th>
                  <th>Current</th>
                  <th>P&L</th>
                  <th>Day %</th>
                </tr>
              </thead>
              <tbody>
                {data.holdings.map((row) => (
                  <tr key={`${row.exchange}-${row.symbol}`}>
                    <td>
                      <span className="mono ticker">{row.symbol}</span>
                      <span className="muted exch">{row.exchange}</span>
                    </td>
                    <td className="mono">{row.quantity}</td>
                    <td className="mono">{money(row.average_price)}</td>
                    <td className="mono">{money(row.last_price)}</td>
                    <td className="mono">{money(row.invested_value)}</td>
                    <td className="mono">{money(row.current_value)}</td>
                    <td className={`mono ${signedClass(row.pnl)}`}>{money(row.pnl)}</td>
                    <td className={`mono ${signedClass(row.day_change_pct)}`}>
                      {money(row.day_change_pct)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section>
        <h3>Open positions ({summary.open_positions})</h3>
        {data.positions.length === 0 ? (
          <p className="muted">No open net positions right now.</p>
        ) : (
          <div className="portfolio-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Product</th>
                  <th>Qty</th>
                  <th>Avg</th>
                  <th>LTP</th>
                  <th>P&L</th>
                </tr>
              </thead>
              <tbody>
                {data.positions.map((row) => (
                  <tr key={`${row.exchange}-${row.symbol}-${row.product}`}>
                    <td className="mono ticker">{row.symbol}</td>
                    <td>{row.product}</td>
                    <td className="mono">{row.quantity}</td>
                    <td className="mono">{money(row.average_price)}</td>
                    <td className="mono">{money(row.last_price)}</td>
                    <td className={`mono ${signedClass(row.pnl)}`}>{money(row.pnl)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <p className="disclaimer muted">
        Read-only view from your Zerodha account. This does not place orders.
      </p>
    </div>
  )
}
