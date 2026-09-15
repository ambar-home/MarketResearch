import { useEffect, useState } from 'react'
import { getProfile } from '../../api/client'
import type { Profile } from '../../api/types'
import './UserTab.css'

export function UserTab() {
  const [profile, setProfile] = useState<Profile | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function load() {
      setLoading(true)
      setError(null)
      try {
        const data = await getProfile()
        if (!cancelled) {
          setProfile(data)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load profile')
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    void load()
    return () => {
      cancelled = true
    }
  }, [])

  if (loading) {
    return <p className="muted">Loading profile…</p>
  }

  if (error) {
    return <div className="alert alert-error">{error}</div>
  }

  if (!profile) {
    return <p className="muted">No profile data.</p>
  }

  return (
    <div className="user-tab">
      <div className="user-hero">
        <div>
          <p className="user-label">User Name</p>
          <h2 className="user-name">{profile.user_name}</h2>
        </div>
        <div>
          <p className="user-label">User ID</p>
          <p className="user-id mono">{profile.user_id}</p>
        </div>
      </div>

      <div className="user-grid">
        <section className="user-section">
          <h3>Products</h3>
          <div className="chip-row">
            {profile.products.length ? (
              profile.products.map((item) => (
                <span className="chip" key={item}>
                  {item}
                </span>
              ))
            ) : (
              <span className="muted">None</span>
            )}
          </div>
        </section>

        <section className="user-section">
          <h3>Exchanges</h3>
          <div className="chip-row">
            {profile.exchanges.length ? (
              profile.exchanges.map((item) => (
                <span className="chip" key={item}>
                  {item}
                </span>
              ))
            ) : (
              <span className="muted">None</span>
            )}
          </div>
        </section>
      </div>

      {(profile.email || profile.broker) && (
        <dl className="user-meta">
          {profile.broker ? (
            <>
              <dt>Broker</dt>
              <dd>{profile.broker}</dd>
            </>
          ) : null}
          {profile.email ? (
            <>
              <dt>Email</dt>
              <dd>{profile.email}</dd>
            </>
          ) : null}
        </dl>
      )}
    </div>
  )
}
