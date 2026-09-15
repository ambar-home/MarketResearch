import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { SignalsTab } from '../components/dashboard/SignalsTab'
import { UserTab } from '../components/dashboard/UserTab'
import { useAuth } from '../context/AuthContext'
import './DashboardPage.css'

type TabId = 'user' | 'signals'

const TABS: { id: TabId; label: string; hint: string }[] = [
  { id: 'user', label: 'User', hint: 'Kite profile details' },
  { id: 'signals', label: 'Signals', hint: 'Nifty 100 SMA crossovers' },
]

export function DashboardPage() {
  const { status, loading, logout } = useAuth()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<TabId>('user')
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
              <h1>Dashboard</h1>
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
        <nav className="dash-tabs" aria-label="Dashboard sections">
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
          ) : (
            <>
              <div className="dash-panel-heading">
                <h2>Signals</h2>
                <p className="muted">
                  Nifty 100 SMA crossover scanner using official index constituents and daily
                  Kite candles.
                </p>
              </div>
              <SignalsTab />
            </>
          )}
        </section>
      </main>
    </div>
  )
}
