import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { BacktestingTab } from '../components/dashboard/BacktestingTab'
import { HourlyTab } from '../components/dashboard/HourlyTab'
import { PortfolioTab } from '../components/dashboard/PortfolioTab'
import { SignalsTab } from '../components/dashboard/SignalsTab'
import { UserTab } from '../components/dashboard/UserTab'
import { useAuth } from '../context/AuthContext'
import './DashboardPage.css'

type TabId = 'user' | 'portfolio' | 'signals' | 'hourly' | 'backtesting'

const TABS: { id: TabId; label: string; hint: string }[] = [
  { id: 'user', label: 'User', hint: 'Kite profile details' },
  { id: 'portfolio', label: 'Portfolio', hint: 'Zerodha holdings' },
  { id: 'signals', label: 'Signals', hint: 'Daily research signals' },
  { id: 'hourly', label: 'Hourly', hint: 'Next-hour research only' },
  { id: 'backtesting', label: 'Backtesting', hint: 'Historical SMA research' },
]

export function DashboardPage() {
  const { status, loading, logout } = useAuth()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<TabId>('signals')
  const [loggingOut, setLoggingOut] = useState(false)

  if (!loading && !status?.authenticated) {
    return <Navigate to="/login" replace />
  }

  async function onLogout() {
    setLoggingOut(true)
    try {
      await logout()
      navigate('/login', { replace: true })
    } finally {
      setLoggingOut(false)
    }
  }

  return (
    <div className="app-shell dashboard">
      <header className="dash-header">
        <div className="container dash-header-inner">
          <div className="dash-brand">
            <div className="dash-mark" aria-hidden="true" />
            <div>
              <p className="dash-eyebrow">MarketResearch</p>
              <h1>Nifty 100 Quantitative Signal Dashboard</h1>
            </div>
          </div>

          <div className="dash-header-actions">
            {status?.user_name ? (
              <span className="dash-user muted">
                Signed in as <strong>{status.user_name}</strong>
              </span>
            ) : null}
            <button
              className="btn btn-ghost"
              type="button"
              onClick={() => void onLogout()}
              disabled={loggingOut}
            >
              {loggingOut ? 'Logging out…' : 'Logout'}
            </button>
          </div>
        </div>
      </header>

      <main className="container dash-main">
        <nav className="dash-tabs dash-tabs-5" aria-label="Dashboard sections">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              className={`dash-tab ${activeTab === tab.id ? 'is-active' : ''}`}
              onClick={() => setActiveTab(tab.id)}
            >
              <span className="dash-tab-label">{tab.label}</span>
              <span className="dash-tab-hint">{tab.hint}</span>
            </button>
          ))}
        </nav>

        <section className="dash-panel" aria-live="polite">
          {activeTab === 'user' ? (
            <>
              <div className="dash-panel-heading">
                <h2>User</h2>
                <p className="muted">Profile data from Kite Connect (`GET /api/profile`).</p>
              </div>
              <UserTab />
            </>
          ) : null}

          {activeTab === 'portfolio' ? (
            <>
              <div className="dash-panel-heading">
                <h2>Portfolio</h2>
                <p className="muted">Read-only holdings and open positions from your Zerodha account.</p>
              </div>
              <PortfolioTab />
            </>
          ) : null}

          {activeTab === 'signals' ? (
            <>
              <div className="dash-panel-heading">
                <h2>Signals</h2>
                <p className="muted">
                  Scored SMA crossover research with trend, volume, momentum, market/sector context
                  and risk references.
                </p>
              </div>
              <SignalsTab />
            </>
          ) : null}

          {activeTab === 'hourly' ? (
            <>
              <div className="dash-panel-heading">
                <h2>Hourly</h2>
                <p className="muted">
                  Separate 5-minute or 15-minute research. It does not use the daily SMA 6/30 score.
                </p>
              </div>
              <HourlyTab />
            </>
          ) : null}

          {activeTab === 'backtesting' ? (
            <>
              <div className="dash-panel-heading">
                <h2>Backtesting</h2>
                <p className="muted">
                  Historical long-only SMA crossover research with transaction costs and slippage.
                </p>
              </div>
              <BacktestingTab />
            </>
          ) : null}
        </section>
      </main>
    </div>
  )
}
