import type {
  AuthStatus,
  BacktestRequest,
  BacktestResponse,
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

export type Holding = {
  symbol: string
  exchange: string
  quantity: number
  average_price: number
  last_price: number
  invested_value: number
  current_value: number
  pnl: number
  day_change_pct: number
  day_pnl: number
}

export type OpenPosition = {
  symbol: string
  exchange: string
  product: string
  quantity: number
  average_price: number
  last_price: number
  pnl: number
  realised: number
  unrealised: number
}

export type Portfolio = {
  summary: {
    holdings_count: number
    open_positions: number
    invested_value: number
    current_value: number
    pnl: number
    pnl_pct: number
    day_pnl: number
  }
  holdings: Holding[]
  positions: OpenPosition[]
}

export function getPortfolio(): Promise<Portfolio> {
  return request<Portfolio>('/api/portfolio')
}

export function generateSmaSignals(
  payload: SmaCrossoverRequest,
): Promise<SmaCrossoverResponse> {
  return request<SmaCrossoverResponse>('/api/signals/sma-crossover', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function runSmaBacktest(payload: BacktestRequest): Promise<BacktestResponse> {
  return request<BacktestResponse>('/api/backtest/sma', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export type StockResearch = {
  ticker: string
  valuation: { flag: string; pe: number | null; reason: string }
  earnings: {
    date: string | null
    days_until: number | null
    event_risk: string
    reason: string
  }
  sentiment: {
    tag: string
    reason: string
    headlines: string[]
  }
  decision: {
    action: 'SKIP' | 'WATCH' | 'RESEARCH_CANDIDATE'
    reasons: string[]
    size_hint: string
  }
  note: string
}

export type JournalAnalysis = {
  logged_with_outcome: number
  high_score_positive_avg_return: number | null
  high_score_positive_count: number
  high_score_other_avg_return: number | null
  high_score_other_count: number
  comparison: string | null
  how_to_read: string
}

export function getStockResearch(
  ticker: string,
  params: {
    score: number
    extension: string
    volume: string
    side: string
    long_sma_direction: string
  },
): Promise<StockResearch> {
  const query = new URLSearchParams({
    score: String(params.score),
    extension: params.extension,
    volume: params.volume,
    side: params.side,
    long_sma_direction: params.long_sma_direction,
  })
  return request<StockResearch>(`/api/research/overlay/${encodeURIComponent(ticker)}?${query}`)
}

export function saveJournal(payload: {
  ticker: string
  score: number
  classification?: string
  sentiment?: string
  valuation_flag?: string
  decision?: string
  notes?: string
}): Promise<{ id: string }> {
  return request('/api/research/journal', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function getJournal(): Promise<{ analysis: JournalAnalysis }> {
  return request('/api/research/journal/list')
}
