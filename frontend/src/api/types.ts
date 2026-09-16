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
  rsi_period?: number
  volume_period?: number
  atr_period?: number
  slope_lookback?: number
  include_market_context?: boolean
  include_sector_context?: boolean
}

export type ScoreBreakdownItem = {
  factor: string
  score: number
  max_score: number
  status: string
  reason: string
}

export type SmaSignalRow = {
  rank: number
  ticker: string
  company: string
  close: number
  crossover?: {
    type: string
    date: string
    days_since: number
  }
  sma?: {
    short_period: number
    short_value: number
    long_period: number
    long_value: number
    spread_pct: number | null
    long_sma_slope_pct: number | null
    long_sma_direction: string
  }
  price_context?: {
    above_long_sma: boolean | null
    distance_from_long_sma_pct: number | null
    extension_status: string
  }
  volume?: {
    current: number | null
    average_20: number | null
    ratio: number | null
    confirmation: string
  }
  momentum?: {
    rsi_14: number | null
    status: string
  }
  volatility?: {
    atr_14: number | null
    atr_pct: number | null
  }
  market?: { trend: string }
  sector?: {
    name: string | null
    trend: string
    available?: boolean
  }
  risk_reward?: {
    entry_reference: number
    stop_reference: number | null
    target_reference: number | null
    risk: number | null
    reward: number | null
    ratio: number | null
    stop_method?: string
    available?: boolean
  }
  signal?: {
    score: number
    classification: string
    summary: string
  }
  score_breakdown?: ScoreBreakdownItem[]
  // backward compatible
  crossover_type?: string
  crossover_date?: string
  sma_short?: number
  sma_long?: number
}

export type ScanSummary = {
  scan_time: string
  scan_duration_seconds?: number
  universe?: string
  stocks_requested: number
  stocks_scanned: number
  stocks_unmapped?: number
  stocks_failed: number
  bullish: number
  bearish: number
  strong_signals: number
  good_signals: number
  moderate_signals: number
  weak_signals: number
  average_score: number
}

export type SmaCrossoverResponse = {
  short_sma: number
  long_sma: number
  lookback_days: number
  max_stocks: number
  rsi_period?: number
  volume_period?: number
  atr_period?: number
  slope_lookback?: number
  scanned: number
  signals_found: number
  errors: number
  scan_summary?: ScanSummary
  market_context?: {
    index?: string
    trend?: string
    close?: number | null
    long_sma?: number | null
    long_sma_direction?: string
    available?: boolean
  }
  signals: SmaSignalRow[]
  failures?: { ticker: string; reason: string }[]
  disclaimer?: string
}

export type BacktestRequest = {
  short_sma: number
  long_sma: number
  start_date: string
  end_date: string
  initial_capital: number
  transaction_costs: boolean
  slippage_bps: number
  max_stocks: number
  compare_combos: boolean
}

export type BacktestResponse = {
  params: Record<string, unknown>
  execution_assumptions: string[]
  metrics: Record<string, number | string | null>
  equity_curve: { date: string; equity: number }[]
  drawdown_curve: { date: string; drawdown_pct: number }[]
  trades: Record<string, unknown>[]
  segments?: Record<string, unknown>
  comparisons?: Record<string, unknown>[]
  comparison_note?: string
  disclaimer?: string
}
