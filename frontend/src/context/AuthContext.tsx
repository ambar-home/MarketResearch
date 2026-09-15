import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import * as api from '../api/client'
import type { AuthStatus, LoginPayload } from '../api/types'

type AuthContextValue = {
  status: AuthStatus | null
  loading: boolean
  error: string | null
  refreshStatus: () => Promise<void>
  login: (payload: LoginPayload) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

const emptyStatus: AuthStatus = {
  authenticated: false,
  user_id: null,
  user_name: null,
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refreshStatus = useCallback(async () => {
    setError(null)
    try {
      const next = await api.getAuthStatus()
      setStatus(next)
    } catch (err) {
      setStatus(emptyStatus)
      setError(err instanceof Error ? err.message : 'Could not reach backend')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refreshStatus()
  }, [refreshStatus])

  const login = useCallback(async (payload: LoginPayload) => {
    setError(null)
    const result = await api.login(payload)
    setStatus({
      authenticated: true,
      user_id: result.user_id,
      user_name: result.user_name,
    })
  }, [])

  const logout = useCallback(async () => {
    setError(null)
    await api.logout()
    setStatus(emptyStatus)
  }, [])

  const value = useMemo(
    () => ({ status, loading, error, refreshStatus, login, logout }),
    [status, loading, error, refreshStatus, login, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth must be used inside AuthProvider')
  }
  return ctx
}
