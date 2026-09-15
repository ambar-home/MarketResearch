import { useState, type FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import './LoginPage.css'

export function LoginPage() {
  const { status, loading, login } = useAuth()
  const navigate = useNavigate()

  const [apiKey, setApiKey] = useState('')
  const [apiSecret, setApiSecret] = useState('')
  const [requestToken, setRequestToken] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!loading && status?.authenticated) {
    return <Navigate to="/dashboard" replace />
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await login({
        api_key: apiKey.trim(),
        api_secret: apiSecret.trim(),
        request_token: requestToken.trim(),
      })
      navigate('/dashboard', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-brand">
          <div className="login-mark" aria-hidden="true" />
          <div>
            <p className="login-eyebrow">MarketResearch</p>
            <h1>Kite Connect Login</h1>
          </div>
        </div>

        <p className="login-copy muted">
          Enter your Zerodha API credentials and a fresh request token. The access
          token is generated and stored on the server only — it never appears in
          the browser.
        </p>

        <form className="login-form" onSubmit={onSubmit}>
          <div className="field">
            <label htmlFor="api_key">API Key</label>
            <input
              id="api_key"
              name="api_key"
              autoComplete="off"
              spellCheck={false}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="Your Kite API key"
              required
            />
          </div>

          <div className="field">
            <label htmlFor="api_secret">API Secret</label>
            <input
              id="api_secret"
              name="api_secret"
              type="password"
              autoComplete="off"
              value={apiSecret}
              onChange={(e) => setApiSecret(e.target.value)}
              placeholder="Your Kite API secret"
              required
            />
          </div>

          <div className="field">
            <label htmlFor="request_token">Request Token</label>
            <input
              id="request_token"
              name="request_token"
              autoComplete="off"
              spellCheck={false}
              value={requestToken}
              onChange={(e) => setRequestToken(e.target.value)}
              placeholder="One-time token from Kite redirect URL"
              required
            />
          </div>

          {error ? <div className="alert alert-error">{error}</div> : null}

          <button className="btn btn-primary login-submit" type="submit" disabled={submitting}>
            {submitting ? 'Signing in…' : 'Login'}
          </button>
        </form>

        <ol className="login-steps muted">
          <li>
            Open{' '}
            <span className="mono">
              https://kite.zerodha.com/connect/login?v=3&amp;api_key=YOUR_API_KEY
            </span>
          </li>
          <li>Approve the login and copy <span className="mono">request_token</span> from the redirect URL.</li>
          <li>Paste it above and click Login. Tokens expire quickly and work only once.</li>
        </ol>
      </div>
    </div>
  )
}
