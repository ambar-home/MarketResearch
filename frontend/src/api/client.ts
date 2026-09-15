import type {
  AuthStatus,
  LoginPayload,
  LoginResponse,
  Profile,
  SmaCrossoverRequest,
  SmaCrossoverResponse,
} from './types'


async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: {
      'Content-Type': 'application/json',
      ...(options?.headers ?? {}),
    },
    ...options,
  })

  const data: unknown = await response.json().catch(() => ({}))

  if (!response.ok) {
    const detail =
      typeof data === 'object' &&
      data !== null &&
      'detail' in data &&
      typeof (data as { detail: unknown }).detail === 'string'
        ? (data as { detail: string }).detail
        : `Request failed (${response.status})`
    throw new Error(detail)
  }

  return data as T
}

export function getAuthStatus(): Promise<AuthStatus> {
  return request<AuthStatus>('/api/auth/status')
}

export function login(payload: LoginPayload): Promise<LoginResponse> {
  return request<LoginResponse>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function logout(): Promise<LoginResponse> {
  return request<LoginResponse>('/api/auth/logout', { method: 'POST' })
}

export function getProfile(): Promise<Profile> {
  return request<Profile>('/api/profile')
}

export function generateSmaSignals(
  payload: SmaCrossoverRequest,
): Promise<SmaCrossoverResponse> {
  return request<SmaCrossoverResponse>('/api/signals/sma-crossover', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
