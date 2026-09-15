export type AuthStatus = {
  authenticated: boolean
  user_id: string | null
  user_name: string | null
}

export type LoginPayload = {
  api_key: string
  api_secret: string
  request_token: string
}

export type LoginResponse = {
  ok: boolean
  message: string
  user_id: string | null
  user_name: string | null
}

export type Profile = {
  user_name: string
  user_id: string
  products: string[]
  exchanges: string[]
  email?: string | null
  broker?: string | null
}

export type ApiError = {
  detail: string
}

export type SmaCrossoverRequest = {
  short_sma: number
  long_sma: number
  lookback_days: number
  max_stocks: number
}

export type SmaSignalRow = {
  rank: number
  ticker: string
  company: string
  crossover_type: string
  crossover_date: string
  close: number
  sma_short: number
  sma_long: number
}

export type SmaCrossoverResponse = {
  short_sma: number
  long_sma: number
  lookback_days: number
  max_stocks: number
  scanned: number
  signals_found: number
  errors: number
  signals: SmaSignalRow[]
}
