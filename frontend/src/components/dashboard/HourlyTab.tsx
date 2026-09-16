import { useState } from 'react'
import './HourlyTab.css'

type HourlyCall = {
  symbol: string
  most_aligned_view: string
  is_actionable: boolean
  why?: string
  price?: number
  spread_bps?: number | null
  avg_volume_20?: number
  atr_pct?: number | null
  news?: { tag: string; summary: string; used_llm: boolean }
  paper?: { shares: number; max_loss: number; costs?: { ok: boolean; reason: string } }
  index_hour?: { bias?: string }
}

type Scan = {
  source: string
  interval: string
  calls: HourlyCall[]
  best: HourlyCall | null
  disclaimer?: string
  separated_from_daily?: string
}

type JournalStats = {
  checked_60m: number
  hit_rate_60m: number | null
  avg_signed_move_60m: number | null
  how_to_read: string
}

async function postJson<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(path, {
    method: body ? 'POST' : 'GET',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(typeof data.detail === 'string' ? data.detail : `Request failed (${response.status})`)
  }
  return data as T
}

export function HourlyTab() {
  const [interval, setInterval] = useState('5minute')
  const [source, setSource] = useState('portfolio')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [scan, setScan] = useState<Scan | null>(null)
  const [stats, setStats] = useState<JournalStats | null>(null)
  const [saved, setSaved] = useState<string | null>(null)

  async function runScan() {
    setLoading(true)
    setError(null)
    setSaved(null)
    try {
      setScan(await postJson<Scan>('/api/hourly/scan', { interval, source, max_stocks: 10 }))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Hourly scan failed')
    } finally {
      setLoading(false)
    }
  }

  async function saveBest() {
    if (!scan?.best) return
    await postJson('/api/hourly/journal', scan.best)
    setSaved(`Saved ${scan.best.symbol} ${scan.best.most_aligned_view} for later checking.`)
  }

  async function checkResults() {
    setError(null)
    try {
      const data = await postJson<{ stats: JournalStats }>('/api/hourly/journal/check', {})
      setStats(data.stats)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not check results')
    }
  }

  const best = scan?.best

  return (
    <div className="hourly-tab">
      <p className="hourly-note">
        This is separate from daily SMA 6/30. The label is the most aligned hourly view, not a
        probability that the price will move.
      </p>
      <div className="hourly-controls">
        <label>
          Bars
          <select value={interval} onChange={(e) => setInterval(e.target.value)}>
            <option value="5minute">5 minute</option>
            <option value="15minute">15 minute</option>
          </select>
        </label>
        <label>
          Universe
          <select value={source} onChange={(e) => setSource(e.target.value)}>
            <option value="portfolio">My holdings</option>
            <option value="nifty">Nifty shortlist</option>
          </select>
        </label>
        <button className="btn btn-primary" type="button" onClick={() => void runScan()} disabled={loading}>
          {loading ? 'Checking…' : 'Run hourly check'}
        </button>
        <button className="btn btn-ghost" type="button" onClick={() => void checkResults()}>
          Check 15/30/60m results
        </button>
      </div>
      {error ? <div className="alert alert-error">{error}</div> : null}

      {best ? (
        <section className="hourly-best">
          <p className="hourly-kicker">Most aligned view</p>
          <h3>
            {best.symbol}: {best.most_aligned_view} over the next hour
          </h3>
          <p>
            Price {best.price} · news {best.news?.tag} · paper size {best.paper?.shares} shares · max
            loss ₹{best.paper?.max_loss}
          </p>
          <p className="muted">{best.news?.summary}</p>
          <button className="btn btn-ghost" type="button" onClick={() => void saveBest()}>
            Save paper journal
          </button>
          {saved ? <p className="muted">{saved}</p> : null}
        </section>
      ) : scan ? (
        <section className="hourly-best">
          <h3>No hourly view</h3>
          <p className="muted">Every name was skipped. That is the safer result when evidence is unclear.</p>
        </section>
      ) : null}

      {scan?.calls?.length ? (
        <div className="portfolio-table-wrap">
          <table>
            <thead>
              <tr>
                <th>Symbol</th>
                <th>View</th>
                <th>Why</th>
                <th>News</th>
                <th>Spread bps</th>
                <th>ATR %</th>
              </tr>
            </thead>
            <tbody>
              {scan.calls.map((row) => (
                <tr key={row.symbol}>
                  <td className="mono">{row.symbol}</td>
                  <td>{row.most_aligned_view}</td>
                  <td>{row.why}</td>
                  <td>{row.news?.tag ?? '—'}</td>
                  <td>{row.spread_bps ?? '—'}</td>
                  <td>{row.atr_pct ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      <section className="hourly-measure">
        <h3>How to measure this</h3>
        <ol>
          <li>Run the check during market hours. If it says SKIP, do nothing.</li>
          <li>If it shows UP or DOWN, save the paper journal. Do not place an order from here.</li>
          <li>After 15, 30, and 60 minutes, click Check results.</li>
          <li>A useful view beats a coin flip only after about 30 checks, and only if the average move still covers costs.</li>
        </ol>
        {stats ? (
          <p>
            Checked 60m samples: {stats.checked_60m}. Hit rate:{' '}
            {stats.hit_rate_60m == null ? 'N/A yet' : `${stats.hit_rate_60m}%`}. Average aligned move:{' '}
            {stats.avg_signed_move_60m ?? 'N/A'}%.
          </p>
        ) : null}
        <p className="muted">{stats?.how_to_read ?? scan?.disclaimer}</p>
      </section>
    </div>
  )
}
